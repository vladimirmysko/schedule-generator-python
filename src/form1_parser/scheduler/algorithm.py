"""Stage 1 scheduling algorithm for multi-group lectures."""

from collections import defaultdict
from datetime import datetime
from pathlib import Path

from .conflicts import ConflictTracker
from .constants import FLEXIBLE_SCHEDULE_SUBJECTS, get_slots_for_shift
from .models import (
    Assignment,
    Day,
    LectureStream,
    PracticalStream,
    Room,
    ScheduleResult,
    ScheduleStatistics,
    UnscheduledReason,
    UnscheduledStream,
    WeekType,
)
from .rooms import RoomManager
from .utils import (
    build_lecture_dependency_map,
    filter_stage1_lectures,
    filter_stage2_practicals,
    load_second_shift_groups,
    sort_streams_by_priority,
)


class Stage1Scheduler:
    """Scheduler for Stage 1: multi-group lectures on Mon/Tue/Wed.

    Stage 1 Requirements:
    1. Filter: Only lectures with 2+ groups
    2. Sort: By largest number of students (descending)
    3. Days: Monday, Tuesday, Wednesday (primary), Thursday, Friday (overflow)
    4. Multi-hour: If odd_week > 1 or even_week > 1, assign 2 back-to-back classes
    5. Even distribution: Each group's lectures evenly distributed among days
    6. Shift start: Lectures begin at the beginning of the shift
    7. Same position: Odd and even weeks use the same (day, slot) for consistency
    8. Room assignment: Assign rooms based on capacity and constraints
    """

    # Stage 1 primary scheduling days
    STAGE1_DAYS = [Day.MONDAY, Day.TUESDAY, Day.WEDNESDAY]

    # Overflow days when primary days are exhausted
    STAGE1_OVERFLOW_DAYS = [Day.THURSDAY, Day.FRIDAY]

    # All weekdays for flexible subjects
    ALL_WEEKDAYS = [Day.MONDAY, Day.TUESDAY, Day.WEDNESDAY, Day.THURSDAY, Day.FRIDAY]

    def _is_flexible_subject(self, subject: str) -> bool:
        """Check if a subject has flexible day scheduling.

        Flexible subjects can be scheduled on any weekday (Mon-Fri)
        and are scheduled with low priority (last).

        Args:
            subject: Subject name to check

        Returns:
            True if subject is in FLEXIBLE_SCHEDULE_SUBJECTS
        """
        return subject in FLEXIBLE_SCHEDULE_SUBJECTS

    def _get_allowed_days(self, subject: str) -> tuple[list[Day], list[Day]]:
        """Get allowed scheduling days for a subject.

        Args:
            subject: Subject name

        Returns:
            Tuple of (primary_days, overflow_days):
            - For flexible subjects: all weekdays as primary, no overflow
            - For regular subjects: Mon/Tue/Wed primary, Thu/Fri overflow
        """
        if self._is_flexible_subject(subject):
            # Flexible subjects can use all weekdays, no overflow needed
            return (self.ALL_WEEKDAYS, [])
        # Regular subjects use standard primary + overflow pattern
        return (self.STAGE1_DAYS, self.STAGE1_OVERFLOW_DAYS)

    def __init__(
        self,
        rooms_csv: Path,
        subject_rooms: dict | None = None,
        instructor_rooms: dict | None = None,
        group_buildings: dict | None = None,
        instructor_availability: list[dict] | None = None,
        nearby_buildings: dict | None = None,
    ) -> None:
        """Initialize the Stage 1 scheduler.

        Args:
            rooms_csv: Path to rooms.csv file
            subject_rooms: Dictionary from subject-rooms.json
            instructor_rooms: Dictionary from instructor-rooms.json
            group_buildings: Dictionary from group-buildings.json
            instructor_availability: List from instructor-availability.json
            nearby_buildings: Dictionary from nearby-buildings.json
        """
        self.instructor_availability = instructor_availability
        self.conflict_tracker = ConflictTracker(
            instructor_availability, nearby_buildings
        )
        self.room_manager = RoomManager(
            rooms_csv, subject_rooms, instructor_rooms, group_buildings
        )

    def schedule(self, streams: list[dict]) -> ScheduleResult:
        """Generate schedule for Stage 1 lectures.

        Args:
            streams: List of stream dictionaries from parsed JSON

        Returns:
            ScheduleResult with assignments and statistics
        """
        # 1. Filter lectures with 2+ groups
        lectures = filter_stage1_lectures(
            streams,
            instructor_availability=self.instructor_availability,
        )

        # 2. Sort by priority (available slots, prac/lab hours, student count)
        prepared = sort_streams_by_priority(lectures)

        # 3. Schedule each stream
        assignments: list[Assignment] = []
        unscheduled_ids: list[str] = []
        unscheduled_streams: list[UnscheduledStream] = []

        for stream in prepared:
            result = self._schedule_stream(stream)
            if isinstance(result, list):
                assignments.extend(result)
            else:
                # result is an UnscheduledStream
                unscheduled_ids.append(stream.id)
                unscheduled_streams.append(result)

        # 4. Compute statistics
        statistics = self._compute_statistics(assignments)

        return ScheduleResult(
            generation_date=datetime.now().isoformat(),
            stage=1,
            assignments=assignments,
            unscheduled_stream_ids=unscheduled_ids,
            unscheduled_streams=unscheduled_streams,
            statistics=statistics,
        )

    def _schedule_stream(
        self, stream: LectureStream
    ) -> list[Assignment] | UnscheduledStream:
        """Schedule a single stream at the same position for both odd and even weeks.

        Args:
            stream: LectureStream to schedule

        Returns:
            List of Assignment objects if scheduled successfully,
            or UnscheduledStream with failure reason if unable to schedule
        """
        # Determine max hours needed (use the larger of odd/even)
        hours = stream.max_hours
        if hours == 0:
            return []

        # Find best position (day, starting_slot)
        position_result = self._find_best_position(stream, hours)

        # Check if we got a position or a failure reason
        # Success returns (Day, int), failure returns (UnscheduledReason, str)
        first_element = position_result[0]
        if isinstance(first_element, Day):
            # Got (day, slot) - successful position found
            day, start_slot = position_result
        else:
            # Got (reason, details) - no position found
            reason, details = position_result
            return UnscheduledStream(
                stream_id=stream.id,
                subject=stream.subject,
                instructor=stream.instructor,
                groups=stream.groups,
                student_count=stream.student_count,
                shift=stream.shift,
                reason=reason,
                details=details,
            )

        assignments = []

        # Find rooms for all consecutive slots, preferring same room
        rooms: list[Room] = []
        preferred_room: Room | None = None

        for i in range(hours):
            slot = start_slot + i

            # Try to use the same room as previous slot
            if preferred_room and self.room_manager.is_room_available(
                preferred_room.name, day, slot, WeekType.BOTH
            ):
                room = preferred_room
            else:
                room = self.room_manager.find_room(stream, day, slot)

            if not room:
                return UnscheduledStream(
                    stream_id=stream.id,
                    subject=stream.subject,
                    instructor=stream.instructor,
                    groups=stream.groups,
                    student_count=stream.student_count,
                    shift=stream.shift,
                    reason=UnscheduledReason.NO_ROOM_AVAILABLE,
                    details=f"No room with capacity >= {stream.student_count} available "
                    f"on {day.value} slot {slot}",
                )

            rooms.append(room)
            preferred_room = room  # Use this room for next slot

        # Create assignments for each slot
        for i in range(hours):
            slot = start_slot + i
            room = rooms[i]

            assignment = Assignment(
                stream_id=stream.id,
                subject=stream.subject,
                instructor=stream.instructor,
                groups=stream.groups,
                student_count=stream.student_count,
                day=day,
                slot=slot,
                room=room.name,
                room_address=room.address,
                week_type=WeekType.BOTH,  # Same position for odd and even weeks
                stream_type="lecture",
            )
            assignments.append(assignment)

            # Reserve resources (including building address for gap constraint)
            self.conflict_tracker.reserve(
                stream.instructor,
                stream.groups,
                day,
                slot,
                WeekType.BOTH,
                building_address=room.address,
            )
            self.room_manager.reserve_room(room, day, slot, WeekType.BOTH)

        return assignments

    def _find_best_position(
        self, stream: LectureStream, hours: int
    ) -> tuple[Day, int] | tuple[UnscheduledReason, str]:
        """Find the best (day, starting_slot) for a stream.

        Strategy:
        1. Get valid slots for the stream's shift
        2. Try primary days (Mon/Tue/Wed) first, sorted by load
        3. If primary days exhausted, try overflow days (Thu/Fri)
        4. Try earliest slots first (start at beginning of shift)
        5. Check consecutive slots if hours > 1

        Args:
            stream: LectureStream to schedule
            hours: Number of consecutive hours needed

        Returns:
            Tuple of (Day, start_slot) if position found, or
            Tuple of (UnscheduledReason, details) if no position found
        """
        # Get valid slots for this stream's shift
        valid_slots = get_slots_for_shift(stream.shift)

        # Get allowed days for this subject (flexible subjects can use all weekdays)
        primary_days, overflow_days = self._get_allowed_days(stream.subject)

        # Try primary days first, then overflow days
        all_days_to_try = primary_days + overflow_days

        # Sort days by total load for these groups (prefer least loaded)
        day_loads = {
            day: self.conflict_tracker.get_groups_total_daily_load(stream.groups, day)
            for day in all_days_to_try
        }

        # Sort primary days by load, then add overflow days at the end
        sorted_primary = sorted(primary_days, key=lambda d: day_loads[d])
        sorted_overflow = sorted(overflow_days, key=lambda d: day_loads[d])
        sorted_days = sorted_primary + sorted_overflow

        # Track why each position failed for detailed reporting
        last_conflict_reason: UnscheduledReason | None = None
        last_conflict_details: str = ""
        positions_tried = 0
        instructor_conflicts = 0
        group_conflicts = 0
        room_conflicts = 0
        building_gap_conflicts = 0
        consecutive_slot_failures = 0
        primary_days_exhausted = False

        for day in sorted_days:
            # Track when we move to overflow days
            if day in overflow_days and not primary_days_exhausted:
                primary_days_exhausted = True

            # Try slots in order (ascending - prefer earliest)
            for slot in valid_slots:
                positions_tried += 1

                # Check if we have enough consecutive slots
                if hours > 1:
                    # Verify all consecutive slots are in valid_slots
                    consecutive_valid = all(
                        (slot + i) in valid_slots for i in range(hours)
                    )
                    if not consecutive_valid:
                        consecutive_slot_failures += 1
                        last_conflict_reason = UnscheduledReason.NO_CONSECUTIVE_SLOTS
                        last_conflict_details = (
                            f"Need {hours} consecutive slots starting at slot {slot} "
                            f"on {day.value}, but only {len(valid_slots)} slots available in shift"
                        )
                        continue

                # Check availability for all consecutive slots with reason tracking
                (
                    slots_available,
                    conflict_reason,
                    conflict_details,
                ) = self.conflict_tracker.check_consecutive_slots_reason(
                    stream.instructor,
                    stream.groups,
                    day,
                    slot,
                    hours,
                    WeekType.BOTH,
                )

                if not slots_available:
                    if conflict_reason == UnscheduledReason.INSTRUCTOR_CONFLICT:
                        instructor_conflicts += 1
                    elif conflict_reason == UnscheduledReason.INSTRUCTOR_UNAVAILABLE:
                        instructor_conflicts += 1
                    elif conflict_reason == UnscheduledReason.GROUP_CONFLICT:
                        group_conflicts += 1
                    last_conflict_reason = conflict_reason
                    last_conflict_details = conflict_details
                    continue

                # Verify rooms are available for all slots (preferring same room)
                rooms_available = True
                first_room = None
                rooms_for_slots: list[Room] = []
                for i in range(hours):
                    if first_room and self.room_manager.is_room_available(
                        first_room.name, day, slot + i, WeekType.BOTH
                    ):
                        rooms_for_slots.append(first_room)
                        continue  # Same room available
                    room = self.room_manager.find_room(stream, day, slot + i)
                    if not room:
                        rooms_available = False
                        room_conflicts += 1
                        last_conflict_reason = UnscheduledReason.NO_ROOM_AVAILABLE
                        last_conflict_details = (
                            f"No room with capacity >= {stream.student_count} available "
                            f"on {day.value} slot {slot + i}"
                        )
                        break
                    rooms_for_slots.append(room)
                    if first_room is None:
                        first_room = room

                if not rooms_available:
                    continue

                # Check building gap constraint for each slot
                building_gap_ok = True
                for i in range(hours):
                    current_slot = slot + i
                    room_address = (
                        rooms_for_slots[i].address if i < len(rooms_for_slots) else None
                    )
                    if room_address:
                        (
                            gap_ok,
                            conflicting_group,
                            gap_details,
                        ) = self.conflict_tracker.check_building_gap_constraint(
                            stream.groups,
                            day,
                            current_slot,
                            room_address,
                            WeekType.BOTH,
                        )
                        if not gap_ok:
                            building_gap_ok = False
                            building_gap_conflicts += 1
                            last_conflict_reason = (
                                UnscheduledReason.BUILDING_GAP_REQUIRED
                            )
                            last_conflict_details = gap_details
                            break

                if building_gap_ok:
                    return (day, slot)

        # No position found - return the most informative failure reason
        if positions_tried == 0:
            return (
                UnscheduledReason.ALL_SLOTS_EXHAUSTED,
                "No valid slots available for this stream's shift",
            )

        # Summarize the conflict patterns
        summary_parts = []
        if instructor_conflicts > 0:
            summary_parts.append(f"instructor conflicts: {instructor_conflicts}")
        if group_conflicts > 0:
            summary_parts.append(f"group conflicts: {group_conflicts}")
        if room_conflicts > 0:
            summary_parts.append(f"room unavailable: {room_conflicts}")
        if building_gap_conflicts > 0:
            summary_parts.append(f"building gap required: {building_gap_conflicts}")
        if consecutive_slot_failures > 0:
            summary_parts.append(
                f"insufficient consecutive slots: {consecutive_slot_failures}"
            )

        summary = (
            f"Tried {positions_tried} positions (including overflow days). "
            + ", ".join(summary_parts)
        )

        # Return the most common/relevant reason
        if last_conflict_reason:
            return (
                last_conflict_reason,
                f"{summary}. Last failure: {last_conflict_details}",
            )

        return (
            UnscheduledReason.ALL_SLOTS_EXHAUSTED,
            f"All {positions_tried} positions exhausted (including Thu/Fri overflow)",
        )

    def _compute_statistics(self, assignments: list[Assignment]) -> ScheduleStatistics:
        """Compute statistics for the generated schedule.

        Args:
            assignments: List of Assignment objects

        Returns:
            ScheduleStatistics object
        """
        by_day: dict[str, int] = defaultdict(int)
        by_shift: dict[str, int] = defaultdict(int)
        room_utilization: dict[str, int] = defaultdict(int)

        for assignment in assignments:
            # Count by day
            by_day[assignment.day.value] += 1

            # Count by shift (determine from slot number)
            if assignment.slot <= 5:
                by_shift["first"] += 1
            else:
                by_shift["second"] += 1

            # Count by room address
            room_utilization[assignment.room_address] += 1

        return ScheduleStatistics(
            by_day=dict(by_day),
            by_shift=dict(by_shift),
            room_utilization=dict(room_utilization),
        )


def create_scheduler(
    rooms_csv: Path | str,
    subject_rooms_json: Path | str | None = None,
    instructor_rooms_json: Path | str | None = None,
    group_buildings_json: Path | str | None = None,
    instructor_availability_json: Path | str | None = None,
    nearby_buildings_json: Path | str | None = None,
) -> Stage1Scheduler:
    """Factory function to create a Stage1Scheduler with loaded reference data.

    Args:
        rooms_csv: Path to rooms.csv file
        subject_rooms_json: Path to subject-rooms.json file (optional)
        instructor_rooms_json: Path to instructor-rooms.json file (optional)
        group_buildings_json: Path to group-buildings.json file (optional)
        instructor_availability_json: Path to instructor-availability.json file (optional)
        nearby_buildings_json: Path to nearby-buildings.json file (optional)

    Returns:
        Configured Stage1Scheduler instance
    """
    import json

    rooms_path = Path(rooms_csv)

    subject_rooms = None
    if subject_rooms_json:
        subject_rooms_path = Path(subject_rooms_json)
        if subject_rooms_path.exists():
            with open(subject_rooms_path, encoding="utf-8") as f:
                subject_rooms = json.load(f)

    instructor_rooms = None
    if instructor_rooms_json:
        instructor_rooms_path = Path(instructor_rooms_json)
        if instructor_rooms_path.exists():
            with open(instructor_rooms_path, encoding="utf-8") as f:
                instructor_rooms = json.load(f)

    group_buildings = None
    if group_buildings_json:
        group_buildings_path = Path(group_buildings_json)
        if group_buildings_path.exists():
            with open(group_buildings_path, encoding="utf-8") as f:
                group_buildings = json.load(f)

    instructor_availability = None
    if instructor_availability_json:
        instructor_availability_path = Path(instructor_availability_json)
        if instructor_availability_path.exists():
            with open(instructor_availability_path, encoding="utf-8") as f:
                instructor_availability = json.load(f)

    nearby_buildings = None
    if nearby_buildings_json:
        nearby_buildings_path = Path(nearby_buildings_json)
        if nearby_buildings_path.exists():
            with open(nearby_buildings_path, encoding="utf-8") as f:
                nearby_buildings = json.load(f)

    return Stage1Scheduler(
        rooms_path,
        subject_rooms,
        instructor_rooms,
        group_buildings,
        instructor_availability,
        nearby_buildings,
    )


class Stage2Scheduler:
    """Scheduler for Stage 2: practice streams with 2+ groups.

    Stage 2 Requirements:
    1. Filter: Only practicals with 2+ groups, has lecture dependency
    2. Sort: By complexity score (most constrained first)
    3. Days: Different day from lecture (preferred), Mon-Fri only
    4. Same shift: Practicals in same shift as group's lecture
    5. 2-hour rule: Max 2 hours per subject per group per day (3 extreme)
    6. Max 6 lessons per day per group
    7. Max 1 window per group per day
    8. Building gap constraints respected
    9. Instructor day constraints respected
    """

    # All weekdays for scheduling (no Saturday)
    WEEKDAYS = [Day.MONDAY, Day.TUESDAY, Day.WEDNESDAY, Day.THURSDAY, Day.FRIDAY]

    def __init__(
        self,
        rooms_csv: Path,
        subject_rooms: dict | None = None,
        instructor_rooms: dict | None = None,
        group_buildings: dict | None = None,
        instructor_availability: list[dict] | None = None,
        nearby_buildings: dict | None = None,
        instructor_day_constraints: list[dict] | None = None,
        second_shift_groups: set[str] | None = None,
    ) -> None:
        """Initialize the Stage 2 scheduler.

        Args:
            rooms_csv: Path to rooms.csv file
            subject_rooms: Dictionary from subject-rooms.json
            instructor_rooms: Dictionary from instructor-rooms.json
            group_buildings: Dictionary from group-buildings.json
            instructor_availability: List from instructor-availability.json
            nearby_buildings: Dictionary from nearby-buildings.json
            instructor_day_constraints: List from instructor-days.json
            second_shift_groups: Set of groups requiring second shift for practicals
        """
        self.instructor_availability = instructor_availability
        self.second_shift_groups = second_shift_groups
        self.conflict_tracker = ConflictTracker(
            instructor_availability, nearby_buildings, instructor_day_constraints
        )
        self.room_manager = RoomManager(
            rooms_csv, subject_rooms, instructor_rooms, group_buildings
        )

    def schedule(
        self,
        streams: list[dict],
        stage1_assignments: list[dict],
    ) -> ScheduleResult:
        """Generate schedule for Stage 2 practicals.

        Args:
            streams: List of stream dictionaries from parsed JSON
            stage1_assignments: List of assignment dicts from Stage 1 schedule

        Returns:
            ScheduleResult with combined Stage 1 + Stage 2 assignments
        """
        # 1. Load Stage 1 assignments into conflict tracker and room manager
        self.conflict_tracker.load_stage1_assignments(stage1_assignments)
        self._load_stage1_rooms(stage1_assignments)

        # 2. Build lecture dependency map
        lecture_dep_map = build_lecture_dependency_map(stage1_assignments)

        # 3. Filter practicals for Stage 2
        practicals = filter_stage2_practicals(
            streams,
            lecture_dep_map,
            self.instructor_availability,
            self.second_shift_groups,
        )

        # 4. Compute viable positions for each stream and sort
        # Streams with fewer viable positions should be scheduled first
        for stream in practicals:
            stream.viable_positions = self._count_viable_positions(stream)

        # Sort by: viable_positions (ascending), then complexity_score (descending)
        sorted_practicals = sorted(
            practicals,
            key=lambda s: (s.viable_positions, -s.complexity_score),
        )

        # 5. Schedule each practical
        new_assignments: list[Assignment] = []
        unscheduled_ids: list[str] = []
        unscheduled_streams: list[UnscheduledStream] = []

        for stream in sorted_practicals:
            result = self._schedule_practical(stream)
            if isinstance(result, list):
                new_assignments.extend(result)
            else:
                unscheduled_ids.append(stream.id)
                unscheduled_streams.append(result)

        # 6. Combine Stage 1 + Stage 2 assignments
        combined_assignments = (
            self._convert_stage1_to_assignments(stage1_assignments) + new_assignments
        )

        # 7. Compute statistics
        statistics = self._compute_statistics(combined_assignments)

        return ScheduleResult(
            generation_date=datetime.now().isoformat(),
            stage=2,
            assignments=combined_assignments,
            unscheduled_stream_ids=unscheduled_ids,
            unscheduled_streams=unscheduled_streams,
            statistics=statistics,
        )

    def _load_stage1_rooms(self, assignments: list[dict]) -> None:
        """Load Stage 1 room assignments into room manager.

        Args:
            assignments: List of assignment dictionaries from Stage 1
        """
        for assignment in assignments:
            day_str = assignment.get("day", "")
            day = Day(day_str)
            slot = assignment.get("slot", 0)
            room_name = assignment.get("room", "")
            week_type_str = assignment.get("week_type", "both")
            week_type = WeekType(week_type_str)

            if room_name:
                # Find room object and reserve it
                room = self.room_manager.get_room_by_name(room_name)
                if room:
                    self.room_manager.reserve_room(room, day, slot, week_type)

    def _convert_stage1_to_assignments(
        self, stage1_assignments: list[dict]
    ) -> list[Assignment]:
        """Convert Stage 1 assignment dicts to Assignment objects.

        Args:
            stage1_assignments: List of assignment dictionaries

        Returns:
            List of Assignment objects
        """
        assignments = []
        for a in stage1_assignments:
            assignment = Assignment(
                stream_id=a.get("stream_id", ""),
                subject=a.get("subject", ""),
                instructor=a.get("instructor", ""),
                groups=a.get("groups", []),
                student_count=a.get("student_count", 0),
                day=Day(a.get("day", "monday")),
                slot=a.get("slot", 0),
                room=a.get("room", ""),
                room_address=a.get("room_address", ""),
                week_type=WeekType(a.get("week_type", "both")),
                stream_type=a.get("stream_type", "lecture"),
            )
            assignments.append(assignment)
        return assignments

    def _schedule_practical(
        self, stream: PracticalStream, remaining_hours: int | None = None
    ) -> list[Assignment] | UnscheduledStream:
        """Schedule a single practical stream.

        Args:
            stream: PracticalStream to schedule
            remaining_hours: If specified, schedule only this many hours (for split scheduling)

        Returns:
            List of Assignment objects if scheduled,
            or UnscheduledStream with failure reason
        """
        hours = remaining_hours if remaining_hours is not None else stream.max_hours
        if hours == 0:
            return []

        if not stream.lecture_dependency:
            return UnscheduledStream(
                stream_id=stream.id,
                subject=stream.subject,
                instructor=stream.instructor,
                groups=stream.groups,
                student_count=stream.student_count,
                shift=stream.shift,
                reason=UnscheduledReason.NO_LECTURE_DEPENDENCY,
                details="No matching lecture found for this practical",
            )

        lecture_day = stream.lecture_dependency.day
        lecture_end_slot = stream.lecture_dependency.end_slot

        # Find best position
        position_result = self._find_best_position(
            stream, lecture_day, lecture_end_slot, hours
        )

        first_element = position_result[0]
        if isinstance(first_element, Day):
            day, start_slot, is_extreme = position_result
        else:
            reason, details = position_result
            # Try splitting: schedule fewer hours, then recurse for remainder
            # NOTE: Do NOT split flexible subjects (PE) - they require consecutive hours
            # in the same location (gym) to avoid unnecessary building transfers
            is_flexible = stream.subject in FLEXIBLE_SCHEDULE_SUBJECTS
            if hours > 1 and not is_flexible:
                for partial_hours in range(hours - 1, 0, -1):
                    partial_result = self._find_best_position(
                        stream, lecture_day, lecture_end_slot, partial_hours
                    )
                    if isinstance(partial_result[0], Day):
                        partial_day, partial_slot, partial_extreme = partial_result
                        partial_assignments = self._create_assignments(
                            stream, partial_day, partial_slot, partial_hours
                        )
                        if isinstance(partial_assignments, list):
                            # Recursively schedule remaining hours
                            remaining = hours - partial_hours
                            rest_result = self._schedule_practical(stream, remaining)
                            if isinstance(rest_result, list):
                                return partial_assignments + rest_result
                            # If rest fails, we already scheduled partial - return what we have
                            # plus info about what couldn't be scheduled
                        break

            return UnscheduledStream(
                stream_id=stream.id,
                subject=stream.subject,
                instructor=stream.instructor,
                groups=stream.groups,
                student_count=stream.student_count,
                shift=stream.shift,
                reason=reason,
                details=details,
            )

        # Successfully found a position - create assignments
        return self._create_assignments(stream, day, start_slot, hours)

    def _create_assignments(
        self,
        stream: PracticalStream,
        day: Day,
        start_slot: int,
        hours: int,
    ) -> list[Assignment] | UnscheduledStream:
        """Create assignments for consecutive hours on a single day.

        Args:
            stream: PracticalStream to schedule
            day: Day to schedule on
            start_slot: Starting slot number
            hours: Number of consecutive hours to schedule

        Returns:
            List of Assignment objects if successful,
            or UnscheduledStream if room allocation fails
        """
        assignments = []

        # Find rooms for all consecutive slots
        rooms: list[Room] = []
        preferred_room: Room | None = None

        for i in range(hours):
            slot = start_slot + i

            if preferred_room and self.room_manager.is_room_available(
                preferred_room.name, day, slot, WeekType.BOTH
            ):
                room = preferred_room
            else:
                room = self.room_manager.find_room_for_practical(stream, day, slot)

            if not room:
                return UnscheduledStream(
                    stream_id=stream.id,
                    subject=stream.subject,
                    instructor=stream.instructor,
                    groups=stream.groups,
                    student_count=stream.student_count,
                    shift=stream.shift,
                    reason=UnscheduledReason.NO_ROOM_AVAILABLE,
                    details=f"No room with capacity >= {stream.student_count} available "
                    f"on {day.value} slot {slot}",
                )

            rooms.append(room)
            preferred_room = room

        # Create assignments
        for i in range(hours):
            slot = start_slot + i
            room = rooms[i]

            assignment = Assignment(
                stream_id=stream.id,
                subject=stream.subject,
                instructor=stream.instructor,
                groups=stream.groups,
                student_count=stream.student_count,
                day=day,
                slot=slot,
                room=room.name,
                room_address=room.address,
                week_type=WeekType.BOTH,
                stream_type=stream.stream_type,
            )
            assignments.append(assignment)

            # Reserve resources
            self.conflict_tracker.reserve(
                stream.instructor,
                stream.groups,
                day,
                slot,
                WeekType.BOTH,
                building_address=room.address,
            )
            self.conflict_tracker.reserve_subject_hours(
                stream.groups, day, stream.subject, 1
            )
            self.room_manager.reserve_room(room, day, slot, WeekType.BOTH)

        return assignments

    def _find_best_position(
        self,
        stream: PracticalStream,
        lecture_day: Day,
        lecture_end_slot: int,
        hours: int,
    ) -> tuple[Day, int, bool] | tuple[UnscheduledReason, str]:
        """Find the best (day, starting_slot) for a practical stream.

        Strategy:
        1. PHASE 1: Try different days after lecture day (preferred)
        2. PHASE 2: Try same day after lecture slot (extreme case, 3 hours allowed)

        Args:
            stream: PracticalStream to schedule
            lecture_day: Day of the dependent lecture
            lecture_end_slot: End slot of the dependent lecture
            hours: Number of consecutive hours needed

        Returns:
            Tuple of (Day, start_slot, is_extreme) if position found, or
            Tuple of (UnscheduledReason, details) if no position found
        """
        valid_slots = get_slots_for_shift(stream.shift)

        # Check if this is a flexible subject (PE)
        is_flexible = stream.subject in FLEXIBLE_SCHEDULE_SUBJECTS

        # Track failure reasons
        last_reason: UnscheduledReason | None = None
        last_details: str = ""
        positions_tried = 0

        # PHASE 1: Try different days (preferred)
        different_days = self._get_days_after(lecture_day)

        # For flexible subjects, all weekdays are available
        if is_flexible:
            different_days = self.WEEKDAYS.copy()

        # Sort days by group daily load (prefer least loaded)
        day_loads = {
            day: self.conflict_tracker.get_groups_total_daily_load(stream.groups, day)
            for day in different_days
        }
        sorted_days = sorted(different_days, key=lambda d: day_loads[d])

        for day in sorted_days:
            for slot in valid_slots:
                # Check if consecutive slots fit in shift
                if hours > 1:
                    consecutive_valid = all(
                        (slot + i) in valid_slots for i in range(hours)
                    )
                    if not consecutive_valid:
                        continue

                positions_tried += 1
                # For PE (flexible subjects) with 3+ hours, use extreme mode (3-hour limit)
                # even on different days, since there's no lecture hour to accumulate
                use_extreme = is_flexible and hours >= 3

                passed, reason, details = self._passes_all_checks(
                    stream, day, slot, hours, extreme=use_extreme
                )

                if passed:
                    return (day, slot, False)

                last_reason = reason
                last_details = details

        # PHASE 2: Try same day after lecture (extreme case)
        same_day_slots = [s for s in valid_slots if s > lecture_end_slot]

        for slot in same_day_slots:
            if hours > 1:
                consecutive_valid = all((slot + i) in valid_slots for i in range(hours))
                if not consecutive_valid:
                    continue

            positions_tried += 1
            passed, reason, details = self._passes_all_checks(
                stream, lecture_day, slot, hours, extreme=True
            )

            if passed:
                return (lecture_day, slot, True)

            last_reason = reason
            last_details = details

        # No position found
        if positions_tried == 0:
            return (
                UnscheduledReason.ALL_SLOTS_EXHAUSTED,
                "No valid slots available for this stream's shift",
            )

        if last_reason:
            return (last_reason, f"Tried {positions_tried} positions. {last_details}")

        return (
            UnscheduledReason.ALL_SLOTS_EXHAUSTED,
            f"All {positions_tried} positions exhausted",
        )

    def _get_days_after(self, lecture_day: Day) -> list[Day]:
        """Get weekdays after the lecture day (different day preference).

        Args:
            lecture_day: The day of the lecture

        Returns:
            List of days after the lecture day (Mon-Fri only)
        """
        day_order = {
            Day.MONDAY: 0,
            Day.TUESDAY: 1,
            Day.WEDNESDAY: 2,
            Day.THURSDAY: 3,
            Day.FRIDAY: 4,
        }

        lecture_idx = day_order.get(lecture_day, 0)

        # Get all days strictly after lecture day
        result = [d for d in self.WEEKDAYS if day_order.get(d, 0) > lecture_idx]

        return result

    def _count_viable_positions(self, stream: PracticalStream) -> int:
        """Count how many day/slot combinations are viable for this stream.

        Used to prioritize streams with fewer options (schedule them first).

        Args:
            stream: PracticalStream to evaluate

        Returns:
            Number of viable starting positions (day + slot combinations)
        """
        if not stream.lecture_dependency:
            return 0

        hours = stream.max_hours
        valid_slots = get_slots_for_shift(stream.shift)
        is_flexible = stream.subject in FLEXIBLE_SCHEDULE_SUBJECTS

        # For flexible subjects, check all weekdays
        days_to_check = (
            self.WEEKDAYS
            if is_flexible
            else self._get_days_after(stream.lecture_dependency.day)
        )

        viable_count = 0
        use_extreme = is_flexible and hours >= 3

        for day in days_to_check:
            for slot in valid_slots:
                # Check if consecutive slots fit
                if hours > 1:
                    if not all((slot + i) in valid_slots for i in range(hours)):
                        continue

                # Check all constraints (without reserving)
                passed, _, _ = self._passes_all_checks(
                    stream, day, slot, hours, extreme=use_extreme
                )
                if passed:
                    viable_count += 1

        return viable_count

    def _passes_all_checks(
        self,
        stream: PracticalStream,
        day: Day,
        slot: int,
        hours: int,
        extreme: bool = False,
    ) -> tuple[bool, UnscheduledReason | None, str]:
        """Check if a position passes all scheduling constraints.

        Args:
            stream: PracticalStream to check
            day: Proposed day
            slot: Proposed starting slot
            hours: Number of consecutive hours
            extreme: If True, allow 3 hours per subject instead of 2

        Returns:
            Tuple of (passed, reason, details)
        """
        # 1. Subject daily hours (2-hour rule, or 3-hour if extreme)
        can_normal, can_extreme = self.conflict_tracker.can_add_subject_hours(
            stream.groups, day, stream.subject, hours
        )
        if extreme:
            if not can_extreme:
                return (
                    False,
                    UnscheduledReason.SUBJECT_DAILY_LIMIT_EXCEEDED,
                    f"Adding {hours} hour(s) would exceed 3-hour limit for subject "
                    f"'{stream.subject}' on {day.value}",
                )
        else:
            if not can_normal:
                return (
                    False,
                    UnscheduledReason.SUBJECT_DAILY_LIMIT_EXCEEDED,
                    f"Adding {hours} hour(s) would exceed 2-hour limit for subject "
                    f"'{stream.subject}' on {day.value}",
                )

        # 2. Daily load (max 6 lessons per group)
        would_exceed, exceed_group = self.conflict_tracker.would_exceed_daily_load(
            stream.groups, day, hours
        )
        if would_exceed:
            return (
                False,
                UnscheduledReason.DAILY_LOAD_EXCEEDED,
                f"Group '{exceed_group}' would exceed 6 lessons on {day.value}",
            )

        # 3. Check each slot
        for i in range(hours):
            current_slot = slot + i

            # 3a. Building gap: is this slot reserved for travel?
            is_gap, gap_group = self.conflict_tracker.is_building_gap_slot(
                stream.groups, day, current_slot
            )
            if is_gap:
                return (
                    False,
                    UnscheduledReason.BUILDING_GAP_REQUIRED,
                    f"Slot {current_slot} is a required travel gap for group '{gap_group}'",
                )

            # 3b. Max windows: would this create a 2nd window?
            would_create, window_group = (
                self.conflict_tracker.would_create_second_window(
                    stream.groups, day, current_slot
                )
            )
            if would_create:
                return (
                    False,
                    UnscheduledReason.MAX_WINDOWS_EXCEEDED,
                    f"Group '{window_group}' would have more than 1 window on {day.value}",
                )

            # 3c. Standard availability (instructor, groups)
            (
                is_available,
                avail_reason,
                avail_details,
            ) = self.conflict_tracker.check_slot_availability_reason(
                stream.instructor, stream.groups, day, current_slot, WeekType.BOTH
            )
            if not is_available:
                return (False, avail_reason, avail_details)

            # 3d. Building gap constraint: check if scheduling at this slot
            # would violate building change time constraint.
            # For multi-hour blocks, we must check each slot (especially the last one)
            # to ensure there's a gap when changing buildings.
            current_room = self.room_manager.find_room_for_practical(
                stream, day, current_slot
            )
            if current_room:
                gap_ok, _, gap_details = (
                    self.conflict_tracker.check_building_gap_constraint(
                        stream.groups,
                        day,
                        current_slot,
                        current_room.address,
                        WeekType.BOTH,
                    )
                )
                if not gap_ok:
                    return (False, UnscheduledReason.BUILDING_GAP_REQUIRED, gap_details)

        # 4. Instructor day constraints
        day_ok, day_details = self.conflict_tracker.check_instructor_day_constraint(
            stream.instructor, day, stream.groups
        )
        if not day_ok:
            return (False, UnscheduledReason.INSTRUCTOR_DAY_CONSTRAINT, day_details)

        # 5. Room availability (quick check for at least one room)
        room = self.room_manager.find_room_for_practical(stream, day, slot)
        if not room:
            return (
                False,
                UnscheduledReason.NO_ROOM_AVAILABLE,
                f"No room with capacity >= {stream.student_count} on {day.value} slot {slot}",
            )

        return (True, None, "")

    def _compute_statistics(self, assignments: list[Assignment]) -> ScheduleStatistics:
        """Compute statistics for the generated schedule.

        Args:
            assignments: List of Assignment objects (Stage 1 + Stage 2)

        Returns:
            ScheduleStatistics object
        """
        by_day: dict[str, int] = defaultdict(int)
        by_shift: dict[str, int] = defaultdict(int)
        room_utilization: dict[str, int] = defaultdict(int)

        for assignment in assignments:
            by_day[assignment.day.value] += 1

            if assignment.slot <= 5:
                by_shift["first"] += 1
            else:
                by_shift["second"] += 1

            room_utilization[assignment.room_address] += 1

        return ScheduleStatistics(
            by_day=dict(by_day),
            by_shift=dict(by_shift),
            room_utilization=dict(room_utilization),
        )


def create_stage2_scheduler(
    rooms_csv: Path | str,
    subject_rooms_json: Path | str | None = None,
    instructor_rooms_json: Path | str | None = None,
    group_buildings_json: Path | str | None = None,
    instructor_availability_json: Path | str | None = None,
    nearby_buildings_json: Path | str | None = None,
    instructor_days_json: Path | str | None = None,
    groups_second_shift_csv: Path | str | None = None,
) -> Stage2Scheduler:
    """Factory function to create a Stage2Scheduler with loaded reference data.

    Args:
        rooms_csv: Path to rooms.csv file
        subject_rooms_json: Path to subject-rooms.json file (optional)
        instructor_rooms_json: Path to instructor-rooms.json file (optional)
        group_buildings_json: Path to group-buildings.json file (optional)
        instructor_availability_json: Path to instructor-availability.json file (optional)
        nearby_buildings_json: Path to nearby-buildings.json file (optional)
        instructor_days_json: Path to instructor-days.json file (optional)
        groups_second_shift_csv: Path to groups-second-shift.csv file (optional)

    Returns:
        Configured Stage2Scheduler instance
    """
    import json

    rooms_path = Path(rooms_csv)

    subject_rooms = None
    if subject_rooms_json:
        subject_rooms_path = Path(subject_rooms_json)
        if subject_rooms_path.exists():
            with open(subject_rooms_path, encoding="utf-8") as f:
                subject_rooms = json.load(f)

    instructor_rooms = None
    if instructor_rooms_json:
        instructor_rooms_path = Path(instructor_rooms_json)
        if instructor_rooms_path.exists():
            with open(instructor_rooms_path, encoding="utf-8") as f:
                instructor_rooms = json.load(f)

    group_buildings = None
    if group_buildings_json:
        group_buildings_path = Path(group_buildings_json)
        if group_buildings_path.exists():
            with open(group_buildings_path, encoding="utf-8") as f:
                group_buildings = json.load(f)

    instructor_availability = None
    if instructor_availability_json:
        instructor_availability_path = Path(instructor_availability_json)
        if instructor_availability_path.exists():
            with open(instructor_availability_path, encoding="utf-8") as f:
                instructor_availability = json.load(f)

    nearby_buildings = None
    if nearby_buildings_json:
        nearby_buildings_path = Path(nearby_buildings_json)
        if nearby_buildings_path.exists():
            with open(nearby_buildings_path, encoding="utf-8") as f:
                nearby_buildings = json.load(f)

    instructor_day_constraints = None
    if instructor_days_json:
        instructor_days_path = Path(instructor_days_json)
        if instructor_days_path.exists():
            with open(instructor_days_path, encoding="utf-8") as f:
                instructor_day_constraints = json.load(f)

    # Load second shift groups
    second_shift_groups = None
    if groups_second_shift_csv:
        groups_second_shift_path = Path(groups_second_shift_csv)
        if groups_second_shift_path.exists():
            second_shift_groups = load_second_shift_groups(groups_second_shift_path)

    return Stage2Scheduler(
        rooms_path,
        subject_rooms,
        instructor_rooms,
        group_buildings,
        instructor_availability,
        nearby_buildings,
        instructor_day_constraints,
        second_shift_groups,
    )
