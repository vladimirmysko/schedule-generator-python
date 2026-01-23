"""Stage 6 scheduler for lab streams.

Stage 6 handles all lab streams with different sub-stages:
- 6A: Multi-group labs (Chemistry - 7 streams)
- 6B: Implicit subgroup labs with room constraint (Physics - 14 streams)
- 6C: Implicit subgroup labs without room constraint (24 streams)
- 6D: Single-group non-subgroup labs (10 streams)

Key constraints:
- C-8.1: No walking subgroups - both subgroups must have lessons in parallel
- C-8.2: Shared instructor subgroups - schedule at day boundaries when same instructor
- C-2.3: Subject room requirements - Physics→306, Chemistry→112
- C-4.1: Instructor availability - check before scheduling
- C-7.2: Daily load - max 6 lessons per group per day
- C-6.1: Shift definitions - maintain shift consistency
"""

import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from .conflicts import ConflictTracker
from .constants import (
    FIRST_SHIFT_EXTENDED_SLOTS,
    FIRST_SHIFT_SLOTS,
    SECOND_SHIFT_SLOTS,
    Shift,
)
from .models import (
    Assignment,
    Day,
    ScheduleResult,
    ScheduleStatistics,
    Stage6LabStream,
    UnscheduledReason,
    UnscheduledStream,
    WeekType,
)
from .rooms import RoomManager
from .utils import (
    build_stage6_subgroup_pairs,
    calculate_stage6_complexity_score,
    categorize_stage6_labs,
    clean_instructor_name,
    filter_stage6_labs,
    sort_stage6_by_complexity,
)

logger = logging.getLogger(__name__)


# Days for lab scheduling (all days Mon-Fri)
STAGE6_DAYS = [Day.MONDAY, Day.TUESDAY, Day.WEDNESDAY, Day.THURSDAY, Day.FRIDAY]

# Day boundary slots for subgroup scheduling (Constraint C-8.2)
# When same instructor teaches both subgroups, schedule at day boundaries
# so idle subgroup can arrive late / leave early
DAY_START_SLOTS_FIRST = [1, 2]  # First shift day start
DAY_END_SLOTS_FIRST = [4, 5]  # First shift day end
DAY_START_SLOTS_SECOND = [6, 7]  # Second shift day start
DAY_END_SLOTS_SECOND = [12, 13]  # Second shift day end


class Stage6Scheduler:
    """Stage 6 scheduler for lab streams."""

    def __init__(
        self,
        room_manager: RoomManager,
        conflict_tracker: ConflictTracker,
        instructor_availability: dict | None = None,
        nearby_buildings: dict | None = None,
        instructor_days: dict | None = None,
        second_shift_groups: set[str] | None = None,
    ) -> None:
        """Initialize Stage 6 scheduler.

        Args:
            room_manager: RoomManager for room allocation
            conflict_tracker: ConflictTracker for conflict detection
            instructor_availability: Optional instructor availability configuration
            nearby_buildings: Optional nearby buildings configuration
            instructor_days: Optional instructor day preferences
            second_shift_groups: Optional set of groups that require second shift
        """
        self.room_manager = room_manager
        self.conflict_tracker = conflict_tracker
        self.instructor_availability = instructor_availability or {}
        self.nearby_buildings = nearby_buildings or {}
        self.instructor_days = instructor_days or {}
        self.second_shift_groups = second_shift_groups or set()
        self.assignments: list[Assignment] = []
        self.unscheduled: list[UnscheduledStream] = []
        self.scheduled_stream_ids: set[str] = set()

    def _load_previous_rooms(self, assignments: list[dict]) -> None:
        """Load previous room assignments into room manager.

        Args:
            assignments: List of assignment dictionaries
        """
        for assignment in assignments:
            day_str = assignment.get("day", "")
            day = Day(day_str)
            slot = assignment.get("slot", 0)
            room_name = assignment.get("room", "")
            week_type_str = assignment.get("week_type", "both")
            week_type = WeekType(week_type_str)

            if room_name:
                room = self.room_manager.get_room_by_name(room_name)
                if room:
                    self.room_manager.reserve_room(room, day, slot, week_type)

    def _get_lecture_days_for_subject(
        self,
        subject: str,
        groups: list[str],
        assignments: list[Assignment],
    ) -> list[Day]:
        """Find days when lectures are scheduled for a subject and group.

        Args:
            subject: Subject name
            groups: List of group names
            assignments: Existing assignments to search

        Returns:
            List of days when lectures are scheduled
        """
        lecture_days: set[Day] = set()

        for assignment in assignments:
            # Check if this is a lecture for the same subject
            if assignment.stream_type != "lecture":
                continue
            if assignment.subject != subject:
                continue

            # Check if any group overlaps
            assignment_groups = set(assignment.groups)
            stream_groups = set(groups)
            if assignment_groups & stream_groups:
                lecture_days.add(assignment.day)

        return list(lecture_days)

    def _get_slots_for_stream(
        self,
        stream: Stage6LabStream,
        extended: bool = True,
    ) -> list[int]:
        """Get valid slots for a stream based on its shift.

        Args:
            stream: Lab stream
            extended: Whether to use extended slots for first shift

        Returns:
            List of valid slot numbers
        """
        if stream.shift == Shift.FIRST:
            return FIRST_SHIFT_EXTENDED_SLOTS if extended else FIRST_SHIFT_SLOTS
        return SECOND_SHIFT_SLOTS

    def _can_schedule_at(
        self,
        stream: Stage6LabStream,
        day: Day,
        slot: int,
        week_type: WeekType,
    ) -> bool:
        """Check if a stream can be scheduled at a specific day/slot.

        Args:
            stream: Lab stream to schedule
            day: Day of week
            slot: Slot number
            week_type: Week type

        Returns:
            True if the stream can be scheduled
        """
        # Check if instructor is available (includes weekly unavailability from JSON)
        if not self.conflict_tracker.is_instructor_available(
            stream.instructor, day, slot, week_type
        ):
            return False

        # Check group availability
        if not self.conflict_tracker.are_groups_available(
            stream.groups, day, slot, week_type
        ):
            return False

        # Check room availability
        room = self.room_manager.find_room_for_stage6(stream, day, slot, week_type)
        if not room:
            return False

        return True

    def _find_day_boundary_positions(
        self,
        stream: Stage6LabStream,
        week_type: WeekType,
        at_start: bool = True,
    ) -> list[tuple[Day, int]]:
        """Find day boundary positions for scheduling subgroups.

        For constraint C-8.2: When same instructor teaches both subgroups,
        schedule one at day start and one at day end.

        Args:
            stream: Lab stream
            week_type: Week type
            at_start: True for day start, False for day end

        Returns:
            List of (day, slot) tuples
        """
        positions = []

        # Get boundary slots based on shift
        if stream.shift == Shift.FIRST:
            boundary_slots = DAY_START_SLOTS_FIRST if at_start else DAY_END_SLOTS_FIRST
        else:
            boundary_slots = (
                DAY_START_SLOTS_SECOND if at_start else DAY_END_SLOTS_SECOND
            )

        # Try each day
        for day in STAGE6_DAYS:
            # Skip lecture days if has dependency (prefer different days)
            if stream.has_lecture_dependency and day in stream.lecture_days:
                continue

            for slot in boundary_slots:
                if self._can_schedule_at(stream, day, slot, week_type):
                    positions.append((day, slot))

        return positions

    def _find_valid_positions(
        self,
        stream: Stage6LabStream,
        week_type: WeekType,
        prefer_after_lecture: bool = True,
    ) -> list[tuple[Day, int]]:
        """Find all valid positions for scheduling a stream.

        Args:
            stream: Lab stream to schedule
            week_type: Week type
            prefer_after_lecture: If True, prefer days after lecture days

        Returns:
            List of (day, slot) tuples, ordered by preference
        """
        positions = []
        slots = self._get_slots_for_stream(stream)

        # Separate days into preferred (after lecture) and non-preferred
        preferred_days = []
        other_days = []

        lecture_days = stream.lecture_days
        lecture_day_indices = {d.value: i for i, d in enumerate(STAGE6_DAYS)}

        for day in STAGE6_DAYS:
            # Check if this day is after any lecture day
            day_idx = lecture_day_indices.get(day.value, 0)

            is_after_lecture = False
            if lecture_days:
                for lecture_day in lecture_days:
                    lecture_idx = lecture_day_indices.get(lecture_day.value, 0)
                    if day_idx > lecture_idx:
                        is_after_lecture = True
                        break

            if prefer_after_lecture and is_after_lecture:
                preferred_days.append(day)
            else:
                other_days.append(day)

        # Try preferred days first, then other days
        for day_list in [preferred_days, other_days]:
            for day in day_list:
                for slot in slots:
                    if self._can_schedule_at(stream, day, slot, week_type):
                        positions.append((day, slot))

        return positions

    def _schedule_stream(
        self,
        stream: Stage6LabStream,
        day: Day,
        slot: int,
        week_type: WeekType,
    ) -> Assignment | None:
        """Schedule a stream at a specific position.

        Args:
            stream: Lab stream to schedule
            day: Day of week
            slot: Slot number
            week_type: Week type

        Returns:
            Assignment if successful, None otherwise
        """
        # Find room
        room = self.room_manager.find_room_for_stage6(stream, day, slot, week_type)
        if not room:
            return None

        # Create assignment
        assignment = Assignment(
            stream_id=stream.id,
            subject=stream.subject,
            instructor=stream.instructor,
            groups=stream.groups,
            stream_type="lab",
            day=day,
            slot=slot,
            week_type=week_type,
            room=room.name,
            room_address=room.address,
            student_count=stream.student_count,
        )

        # Reserve room and update conflict tracker
        self.room_manager.reserve_room(room, day, slot, week_type)
        self.conflict_tracker.reserve(
            stream.instructor,
            stream.groups,
            day,
            slot,
            week_type,
            building_address=room.address,
        )
        self.conflict_tracker.reserve_subject_hours(
            stream.groups, day, stream.subject, 1
        )
        self.assignments.append(assignment)
        self.scheduled_stream_ids.add(stream.id)

        return assignment

    def _schedule_multi_group_lab(
        self,
        stream: Stage6LabStream,
    ) -> bool:
        """Schedule a multi-group lab (Stage 6A).

        Multi-group labs are typically Chemistry labs that require room 112.

        Args:
            stream: Multi-group lab stream

        Returns:
            True if scheduled successfully
        """
        # Determine week types to schedule
        week_types = []
        if stream.hours_odd_week > 0 and stream.hours_even_week > 0:
            # Both weeks - schedule both
            week_types = [WeekType.ODD, WeekType.EVEN]
        elif stream.hours_odd_week > 0:
            week_types = [WeekType.ODD]
        elif stream.hours_even_week > 0:
            week_types = [WeekType.EVEN]
        else:
            # No hours, skip
            return False

        scheduled_any = False
        for week_type in week_types:
            hours_needed = (
                stream.hours_odd_week
                if week_type == WeekType.ODD
                else stream.hours_even_week
            )

            for _ in range(hours_needed):
                positions = self._find_valid_positions(
                    stream, week_type, prefer_after_lecture=True
                )

                if positions:
                    day, slot = positions[0]
                    assignment = self._schedule_stream(stream, day, slot, week_type)
                    if assignment:
                        scheduled_any = True
                        logger.debug(
                            f"Scheduled multi-group lab {stream.id} on {day.value} slot {slot} ({week_type.value})"
                        )
                else:
                    self.unscheduled.append(
                        UnscheduledStream(
                            stream_id=stream.id,
                            subject=stream.subject,
                            instructor=stream.instructor,
                            groups=stream.groups,
                            student_count=stream.student_count,
                            shift=stream.shift,
                            reason=UnscheduledReason.ALL_SLOTS_EXHAUSTED,
                            details=f"No position found for {week_type.value} week",
                        )
                    )

        return scheduled_any

    def _schedule_subgroup_pair_at_boundaries(
        self,
        stream1: Stage6LabStream,
        stream2: Stage6LabStream,
    ) -> bool:
        """Schedule a subgroup pair using day boundary strategy.

        For constraint C-8.2: When same instructor teaches both subgroups,
        schedule one at day START and one at day END so idle subgroup
        can arrive late / leave early.

        Args:
            stream1: First subgroup stream
            stream2: Second subgroup stream

        Returns:
            True if both scheduled successfully
        """
        # Determine week types
        week_types = []
        if stream1.hours_odd_week > 0 or stream2.hours_odd_week > 0:
            week_types.append(WeekType.ODD)
        if stream1.hours_even_week > 0 or stream2.hours_even_week > 0:
            week_types.append(WeekType.EVEN)

        if not week_types:
            return False

        scheduled_any = False
        for week_type in week_types:
            hours1 = (
                stream1.hours_odd_week
                if week_type == WeekType.ODD
                else stream1.hours_even_week
            )
            hours2 = (
                stream2.hours_odd_week
                if week_type == WeekType.ODD
                else stream2.hours_even_week
            )

            hours_to_schedule = max(hours1, hours2)

            for _ in range(hours_to_schedule):
                # Find day where both can be scheduled
                found_day = False
                for day in STAGE6_DAYS:
                    # Skip lecture days if has dependency
                    if stream1.has_lecture_dependency and day in stream1.lecture_days:
                        continue

                    # Find boundary positions for this day
                    start_positions = self._find_day_boundary_positions(
                        stream1, week_type, at_start=True
                    )
                    end_positions = self._find_day_boundary_positions(
                        stream2, week_type, at_start=False
                    )

                    # Filter to this day only
                    start_for_day = [(d, s) for d, s in start_positions if d == day]
                    end_for_day = [(d, s) for d, s in end_positions if d == day]

                    if start_for_day and end_for_day:
                        # Schedule stream1 at day start
                        day1, slot1 = start_for_day[0]
                        assignment1 = self._schedule_stream(
                            stream1, day1, slot1, week_type
                        )

                        if assignment1:
                            # Schedule stream2 at day end
                            # Re-check positions after stream1 is scheduled
                            end_positions_updated = self._find_day_boundary_positions(
                                stream2, week_type, at_start=False
                            )
                            end_for_day_updated = [
                                (d, s) for d, s in end_positions_updated if d == day
                            ]

                            if end_for_day_updated:
                                day2, slot2 = end_for_day_updated[0]
                                assignment2 = self._schedule_stream(
                                    stream2, day2, slot2, week_type
                                )
                                if assignment2:
                                    scheduled_any = True
                                    found_day = True
                                    logger.debug(
                                        f"Scheduled subgroup pair {stream1.id} (slot {slot1}) and {stream2.id} (slot {slot2}) on {day.value}"
                                    )
                                    break

                if not found_day:
                    # Try regular scheduling as fallback
                    positions1 = self._find_valid_positions(stream1, week_type)
                    if positions1:
                        day1, slot1 = positions1[0]
                        self._schedule_stream(stream1, day1, slot1, week_type)
                        scheduled_any = True

                    positions2 = self._find_valid_positions(stream2, week_type)
                    if positions2:
                        day2, slot2 = positions2[0]
                        self._schedule_stream(stream2, day2, slot2, week_type)
                        scheduled_any = True

        return scheduled_any

    def _schedule_implicit_subgroup_lab(
        self,
        stream: Stage6LabStream,
        pair_streams: list[Stage6LabStream],
    ) -> bool:
        """Schedule an implicit subgroup lab (Stage 6B/6C).

        Args:
            stream: Implicit subgroup stream
            pair_streams: All streams in this subgroup pair

        Returns:
            True if scheduled successfully
        """
        # Check if this is a critical pair (same instructor)
        if stream.is_critical_pair and stream.paired_stream_id:
            # Find paired stream
            paired = None
            for s in pair_streams:
                if s.id == stream.paired_stream_id:
                    paired = s
                    break

            if paired and stream.id not in self.scheduled_stream_ids:
                if paired.id not in self.scheduled_stream_ids:
                    return self._schedule_subgroup_pair_at_boundaries(stream, paired)

        # Not a critical pair or paired stream already scheduled
        # Use regular scheduling
        week_types = []
        if stream.hours_odd_week > 0:
            week_types.append(WeekType.ODD)
        if stream.hours_even_week > 0:
            week_types.append(WeekType.EVEN)

        scheduled_any = False
        for week_type in week_types:
            hours = (
                stream.hours_odd_week
                if week_type == WeekType.ODD
                else stream.hours_even_week
            )

            for _ in range(hours):
                positions = self._find_valid_positions(
                    stream, week_type, prefer_after_lecture=True
                )

                if positions:
                    day, slot = positions[0]
                    assignment = self._schedule_stream(stream, day, slot, week_type)
                    if assignment:
                        scheduled_any = True
                else:
                    self.unscheduled.append(
                        UnscheduledStream(
                            stream_id=stream.id,
                            subject=stream.subject,
                            instructor=stream.instructor,
                            groups=stream.groups,
                            student_count=stream.student_count,
                            shift=stream.shift,
                            reason=UnscheduledReason.ALL_SLOTS_EXHAUSTED,
                            details=f"No position found for {week_type.value} week",
                        )
                    )

        return scheduled_any

    def _schedule_single_group_lab(
        self,
        stream: Stage6LabStream,
    ) -> bool:
        """Schedule a single-group non-subgroup lab (Stage 6D).

        Args:
            stream: Single-group lab stream

        Returns:
            True if scheduled successfully
        """
        week_types = []
        if stream.hours_odd_week > 0:
            week_types.append(WeekType.ODD)
        if stream.hours_even_week > 0:
            week_types.append(WeekType.EVEN)

        scheduled_any = False
        for week_type in week_types:
            hours = (
                stream.hours_odd_week
                if week_type == WeekType.ODD
                else stream.hours_even_week
            )

            for _ in range(hours):
                positions = self._find_valid_positions(
                    stream, week_type, prefer_after_lecture=True
                )

                if positions:
                    day, slot = positions[0]
                    assignment = self._schedule_stream(stream, day, slot, week_type)
                    if assignment:
                        scheduled_any = True
                else:
                    self.unscheduled.append(
                        UnscheduledStream(
                            stream_id=stream.id,
                            subject=stream.subject,
                            instructor=stream.instructor,
                            groups=stream.groups,
                            student_count=stream.student_count,
                            shift=stream.shift,
                            reason=UnscheduledReason.ALL_SLOTS_EXHAUSTED,
                            details=f"No position found for {week_type.value} week",
                        )
                    )

        return scheduled_any

    def schedule(
        self,
        streams: list[dict],
        previous_assignments: list[dict],
        previous_unscheduled: list[dict] | None = None,
    ) -> ScheduleResult:
        """Schedule all Stage 6 lab streams.

        Args:
            streams: List of all stream dictionaries from parsed JSON
            previous_assignments: Assignments from previous stages
            previous_unscheduled: Unscheduled streams from previous stages

        Returns:
            ScheduleResult with Stage 6 assignments added
        """
        # Initialize with previous assignments
        scheduled_stream_ids = {a["stream_id"] for a in previous_assignments}

        # Load previous assignments into conflict tracker and room manager
        self.conflict_tracker.load_stage1_assignments(previous_assignments)
        self._load_previous_rooms(previous_assignments)

        # Convert previous assignments to Assignment objects
        for assignment_dict in previous_assignments:
            assignment = Assignment(
                stream_id=assignment_dict["stream_id"],
                subject=assignment_dict["subject"],
                instructor=assignment_dict["instructor"],
                groups=assignment_dict["groups"],
                stream_type=assignment_dict["stream_type"],
                day=Day(assignment_dict["day"]),
                slot=assignment_dict["slot"],
                week_type=WeekType(assignment_dict["week_type"]),
                room=assignment_dict["room"],
                room_address=assignment_dict.get("room_address", ""),
                student_count=assignment_dict.get("student_count", 0),
            )
            self.assignments.append(assignment)

        self.scheduled_stream_ids = scheduled_stream_ids

        # Carry over previous unscheduled
        if previous_unscheduled:
            for unscheduled_dict in previous_unscheduled:
                self.unscheduled.append(
                    UnscheduledStream(
                        stream_id=unscheduled_dict["stream_id"],
                        subject=unscheduled_dict.get("subject", ""),
                        instructor=unscheduled_dict.get("instructor", ""),
                        groups=unscheduled_dict.get("groups", []),
                        student_count=unscheduled_dict.get("student_count", 0),
                        shift=Shift(unscheduled_dict.get("shift", "first")),
                        reason=UnscheduledReason(
                            unscheduled_dict.get("reason", "unknown")
                        ),
                        details=unscheduled_dict.get("details", ""),
                    )
                )

        # Get subjects with lectures
        subjects_with_lectures = {
            a["subject"] for a in previous_assignments if a["stream_type"] == "lecture"
        }

        # Filter and prepare Stage 6 streams
        stage6_streams = filter_stage6_labs(
            streams,
            scheduled_stream_ids,
            subjects_with_lectures,
            self.instructor_availability,
            self.second_shift_groups,
        )

        if not stage6_streams:
            logger.info("No Stage 6 lab streams to schedule")
            return self._build_result(streams)

        logger.info(f"Found {len(stage6_streams)} Stage 6 lab streams")

        # Build subgroup pairs
        subgroup_pairs = build_stage6_subgroup_pairs(stage6_streams)

        # Set lecture days for each stream
        for stream in stage6_streams:
            stream.lecture_days = self._get_lecture_days_for_subject(
                stream.subject, stream.groups, self.assignments
            )

        # Calculate complexity scores
        instructor_stream_counts: dict[str, int] = defaultdict(int)
        for stream in stage6_streams:
            clean_name = clean_instructor_name(stream.instructor)
            instructor_stream_counts[clean_name] += 1

        for stream in stage6_streams:
            clean_name = clean_instructor_name(stream.instructor)
            stream.complexity_score = calculate_stage6_complexity_score(
                stream,
                group_available_slots=35,  # Default
                instructor_unavailable_slots=65 - stream.instructor_available_slots,
                instructor_stream_count=instructor_stream_counts.get(clean_name, 1),
            )

        # Categorize streams
        categories = categorize_stage6_labs(stage6_streams)

        # Stage 6A: Multi-group labs
        logger.info(
            f"Stage 6A: Scheduling {len(categories['multi_group'])} multi-group labs"
        )
        for stream in sort_stage6_by_complexity(categories["multi_group"]):
            if stream.id not in self.scheduled_stream_ids:
                self._schedule_multi_group_lab(stream)

        # Stage 6B: Implicit subgroup labs with room constraint
        logger.info(
            f"Stage 6B: Scheduling {len(categories['implicit_subgroup_constrained'])} "
            "implicit subgroup labs with room constraint"
        )
        for stream in sort_stage6_by_complexity(
            categories["implicit_subgroup_constrained"]
        ):
            if stream.id not in self.scheduled_stream_ids:
                pair_key = (
                    f"{stream.base_groups[0]}:{stream.subject}"
                    if stream.base_groups
                    else None
                )
                pair_streams = subgroup_pairs.get(pair_key, [stream])
                self._schedule_implicit_subgroup_lab(stream, pair_streams)

        # Stage 6C: Implicit subgroup labs without room constraint
        logger.info(
            f"Stage 6C: Scheduling {len(categories['implicit_subgroup'])} "
            "implicit subgroup labs without room constraint"
        )
        for stream in sort_stage6_by_complexity(categories["implicit_subgroup"]):
            if stream.id not in self.scheduled_stream_ids:
                pair_key = (
                    f"{stream.base_groups[0]}:{stream.subject}"
                    if stream.base_groups
                    else None
                )
                pair_streams = subgroup_pairs.get(pair_key, [stream])
                self._schedule_implicit_subgroup_lab(stream, pair_streams)

        # Stage 6D: Single-group non-subgroup labs
        logger.info(
            f"Stage 6D: Scheduling {len(categories['single_group'])} single-group labs"
        )
        for stream in sort_stage6_by_complexity(categories["single_group"]):
            if stream.id not in self.scheduled_stream_ids:
                self._schedule_single_group_lab(stream)

        return self._build_result(streams)

    def _build_result(self, streams: list[dict]) -> ScheduleResult:
        """Build the schedule result.

        Args:
            streams: Original stream dictionaries

        Returns:
            ScheduleResult object
        """
        # Calculate statistics
        by_day: dict[str, int] = defaultdict(int)
        by_shift: dict[str, int] = defaultdict(int)
        room_utilization: dict[str, int] = defaultdict(int)

        # Count only Stage 6 assignments
        stage6_stream_ids = {s["id"] for s in streams if s.get("stream_type") == "lab"}

        expected_hours = 0
        scheduled_hours = 0

        for stream in streams:
            if stream.get("stream_type") != "lab":
                continue
            hours = stream.get("hours", {})
            expected_hours += hours.get("odd_week", 0) + hours.get("even_week", 0)

        for assignment in self.assignments:
            if assignment.stream_id in stage6_stream_ids:
                by_day[assignment.day.value] += 1
                # Determine shift from slot number
                if assignment.slot <= 5:
                    by_shift["first"] += 1
                else:
                    by_shift["second"] += 1
                room_utilization[assignment.room_address] += 1
                scheduled_hours += 1

        statistics = ScheduleStatistics(
            by_day=dict(by_day),
            by_shift=dict(by_shift),
            room_utilization=dict(room_utilization),
            expected_hours=expected_hours,
            scheduled_hours=scheduled_hours,
        )

        return ScheduleResult(
            generation_date=datetime.now().isoformat(),
            stage=6,
            assignments=self.assignments,
            unscheduled_streams=self.unscheduled,
            unscheduled_stream_ids=[u.stream_id for u in self.unscheduled],
            statistics=statistics,
        )


def create_stage6_scheduler(
    rooms_csv: Path,
    subject_rooms_path: Path | None = None,
    instructor_rooms_path: Path | None = None,
    group_buildings_path: Path | None = None,
    instructor_availability_path: Path | None = None,
    nearby_buildings_path: Path | None = None,
    instructor_days_path: Path | None = None,
    groups_second_shift_path: Path | None = None,
) -> Stage6Scheduler:
    """Create a Stage 6 scheduler with all dependencies.

    Args:
        rooms_csv: Path to rooms.csv file
        subject_rooms_path: Optional path to subject-rooms.json
        instructor_rooms_path: Optional path to instructor-rooms.json
        group_buildings_path: Optional path to group-buildings.json
        instructor_availability_path: Optional path to instructor-availability.json
        nearby_buildings_path: Optional path to nearby-buildings.json
        instructor_days_path: Optional path to instructor-days.json
        groups_second_shift_path: Optional path to groups-second-shift.csv

    Returns:
        Configured Stage6Scheduler instance
    """
    # Load configuration files
    subject_rooms = None
    instructor_rooms = None
    group_buildings = None
    instructor_availability = None
    nearby_buildings = None
    instructor_days = None
    second_shift_groups: set[str] = set()

    if subject_rooms_path and subject_rooms_path.exists():
        with open(subject_rooms_path, encoding="utf-8") as f:
            subject_rooms = json.load(f)

    if instructor_rooms_path and instructor_rooms_path.exists():
        with open(instructor_rooms_path, encoding="utf-8") as f:
            instructor_rooms = json.load(f)

    if group_buildings_path and group_buildings_path.exists():
        with open(group_buildings_path, encoding="utf-8") as f:
            group_buildings = json.load(f)

    if instructor_availability_path and instructor_availability_path.exists():
        with open(instructor_availability_path, encoding="utf-8") as f:
            instructor_availability = json.load(f)

    if nearby_buildings_path and nearby_buildings_path.exists():
        with open(nearby_buildings_path, encoding="utf-8") as f:
            nearby_buildings = json.load(f)

    if instructor_days_path and instructor_days_path.exists():
        with open(instructor_days_path, encoding="utf-8") as f:
            instructor_days = json.load(f)

    if groups_second_shift_path and groups_second_shift_path.exists():
        import csv

        with open(groups_second_shift_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                group = row.get("group", "").strip()
                if group:
                    second_shift_groups.add(group)

    # Create room manager
    room_manager = RoomManager(
        rooms_csv,
        subject_rooms=subject_rooms,
        instructor_rooms=instructor_rooms,
        group_buildings=group_buildings,
    )

    # Create conflict tracker
    conflict_tracker = ConflictTracker()

    return Stage6Scheduler(
        room_manager=room_manager,
        conflict_tracker=conflict_tracker,
        instructor_availability=instructor_availability,
        nearby_buildings=nearby_buildings,
        instructor_days=instructor_days,
        second_shift_groups=second_shift_groups,
    )
