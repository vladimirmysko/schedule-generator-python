"""Stage 5 scheduling algorithm for single-group practicals with lecture dependency."""

from collections import defaultdict
from datetime import datetime
from pathlib import Path

from .conflicts import ConflictTracker
from .constants import Shift, get_slots_for_shift
from .models import (
    Assignment,
    Day,
    Room,
    ScheduleResult,
    ScheduleStatistics,
    Stage5PracticalStream,
    UnscheduledReason,
    UnscheduledStream,
    WeekType,
)
from .rooms import RoomManager
from .utils import (
    STAGE5_PE_SUBJECTS,
    build_scheduled_lecture_days,
    build_stage5_subgroup_pairs,
    build_subjects_with_lectures,
    calculate_stage5_complexity_score,
    clean_instructor_name,
    filter_stage5_practicals,
    load_second_shift_groups,
    sort_stage5_by_complexity,
)


class Stage5Scheduler:
    """Scheduler for Stage 5: single-group practicals with lecture dependency.

    Handles ~450 practical streams with exactly 1 group that have
    corresponding lectures scheduled in previous stages.

    Key features:
    1. Lecture dependency - prefers days WITHOUT lectures for the subject
    2. Can use any weekday (Mon-Fri)
    3. Subgroup pairing - different instructors can run in parallel
    4. PE streams scheduled last (most flexible)
    5. Gap-filling strategy (prefer days with existing classes)
    """

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
        """Initialize the Stage 5 scheduler.

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
        self.subject_rooms = subject_rooms or {}
        self.conflict_tracker = ConflictTracker(
            instructor_availability, nearby_buildings, instructor_day_constraints
        )
        self.room_manager = RoomManager(
            rooms_csv, subject_rooms, instructor_rooms, group_buildings
        )
        # Track scheduled subgroup pairs to coordinate parallel scheduling
        self._subgroup_schedule: dict[
            str, tuple[Day, int]
        ] = {}  # stream_id -> (day, slot)
        # Track lecture days per subject for scheduling preference
        self._lecture_days: dict[str, list[Day]] = {}

    def schedule(
        self,
        streams: list[dict],
        previous_assignments: list[dict],
        previous_unscheduled: list[dict] | None = None,
    ) -> ScheduleResult:
        """Generate schedule for Stage 5 single-group practicals.

        Args:
            streams: List of stream dictionaries from parsed JSON
            previous_assignments: List of assignment dicts from Stage 1-4 schedule
            previous_unscheduled: List of unscheduled stream dicts from Stage 4 (optional)

        Returns:
            ScheduleResult with combined previous + Stage 5 assignments
        """
        # 1. Load previous assignments into conflict tracker and room manager
        self.conflict_tracker.load_stage1_assignments(previous_assignments)
        self._load_previous_rooms(previous_assignments)

        # 2. Build set of already scheduled stream IDs
        scheduled_ids = {a.get("stream_id", "") for a in previous_assignments}

        # 3. Build mapping of subject -> lecture days
        self._lecture_days = build_scheduled_lecture_days(previous_assignments)

        # 4. Build set of subjects that have lectures
        subjects_with_lectures = build_subjects_with_lectures(streams)
        # Add subjects from scheduled lectures (some may not be in parsed streams)
        for subject in self._lecture_days.keys():
            subjects_with_lectures.add(subject)

        # 5. Filter single-group practicals for Stage 5
        practicals = filter_stage5_practicals(
            streams,
            scheduled_ids,
            subjects_with_lectures,
            self.instructor_availability,
            self.second_shift_groups,
        )

        # 6. Set lecture days on streams
        for stream in practicals:
            stream.lecture_days = self._lecture_days.get(stream.subject, [])

        # 7. Build subgroup pairs and identify critical pairs
        subgroup_pairs = build_stage5_subgroup_pairs(practicals)

        # 8. Compute complexity scores
        instructor_stream_counts = self._count_instructor_streams(practicals)
        group_slot_availability = self._compute_group_availability(practicals)

        for stream in practicals:
            instructor_count = instructor_stream_counts.get(stream.instructor, 1)
            group_slots = group_slot_availability.get(stream.groups[0], 35)
            has_room_constraint = stream.subject in self.subject_rooms
            is_pe = stream.subject in STAGE5_PE_SUBJECTS

            # Calculate unavailable slots from instructor availability
            unavailable = 0
            if self.instructor_availability:
                clean_name = clean_instructor_name(stream.instructor)
                for record in self.instructor_availability:
                    if record.get("name") == clean_name:
                        weekly = record.get("weekly_unavailable", {})
                        for day in [
                            "monday",
                            "tuesday",
                            "wednesday",
                            "thursday",
                            "friday",
                        ]:
                            unavailable += len(weekly.get(day, []))
                        break

            stream.complexity_score = calculate_stage5_complexity_score(
                stream,
                group_available_slots=group_slots,
                instructor_unavailable_slots=unavailable,
                instructor_stream_count=instructor_count,
                subject_has_room_constraints=has_room_constraint,
                is_pe_subject=is_pe,
            )
            stream.group_available_slots = group_slots

        sorted_practicals = sort_stage5_by_complexity(practicals)

        # 9. Calculate expected hours for this stage
        expected_hours = sum(stream.max_hours for stream in sorted_practicals)

        # 10. Schedule each practical
        new_assignments: list[Assignment] = []
        unscheduled_ids: list[str] = []
        unscheduled_streams: list[UnscheduledStream] = []
        scheduled_stream_ids: set[str] = set()

        for stream in sorted_practicals:
            # Skip if already scheduled (e.g., as part of a pair)
            if stream.id in scheduled_stream_ids:
                continue

            result = self._schedule_stream(stream, subgroup_pairs, scheduled_stream_ids)
            if isinstance(result, list):
                new_assignments.extend(result)
                for a in result:
                    scheduled_stream_ids.add(a.stream_id)
            else:
                unscheduled_ids.append(stream.id)
                unscheduled_streams.append(result)

        # 11. Calculate scheduled hours (number of new assignments)
        scheduled_hours = len(new_assignments)

        # 12. Combine previous + Stage 5 assignments
        combined_assignments = (
            self._convert_to_assignments(previous_assignments) + new_assignments
        )

        # 13. Combine previous + Stage 5 unscheduled streams
        all_unscheduled_ids = unscheduled_ids.copy()
        all_unscheduled_streams = unscheduled_streams.copy()

        if previous_unscheduled:
            for u in previous_unscheduled:
                all_unscheduled_ids.append(u.get("stream_id", ""))
                all_unscheduled_streams.append(
                    UnscheduledStream(
                        stream_id=u.get("stream_id", ""),
                        subject=u.get("subject", ""),
                        instructor=u.get("instructor", ""),
                        groups=u.get("groups", []),
                        student_count=u.get("student_count", 0),
                        shift=Shift(u.get("shift", "first")),
                        reason=UnscheduledReason(
                            u.get("reason", "all_slots_exhausted")
                        ),
                        details=u.get("details", ""),
                    )
                )

        # 14. Compute statistics
        statistics = self._compute_statistics(
            combined_assignments, expected_hours, scheduled_hours
        )

        return ScheduleResult(
            generation_date=datetime.now().isoformat(),
            stage=5,
            assignments=combined_assignments,
            unscheduled_stream_ids=all_unscheduled_ids,
            unscheduled_streams=all_unscheduled_streams,
            statistics=statistics,
        )

    def _count_instructor_streams(
        self, streams: list[Stage5PracticalStream]
    ) -> dict[str, int]:
        """Count how many streams each instructor has.

        Args:
            streams: List of Stage5PracticalStream objects

        Returns:
            Dict mapping instructor name to stream count
        """
        counts: dict[str, int] = defaultdict(int)
        for stream in streams:
            counts[stream.instructor] += 1
        return counts

    def _compute_group_availability(
        self, streams: list[Stage5PracticalStream]
    ) -> dict[str, int]:
        """Compute available slots for each group.

        Args:
            streams: List of Stage5PracticalStream objects

        Returns:
            Dict mapping group name to available slot count
        """
        availability: dict[str, int] = {}

        for stream in streams:
            for group in stream.groups:
                if group in availability:
                    continue

                # Count available slots on all weekdays
                total_slots = 0
                valid_slots = get_slots_for_shift(stream.shift)

                for day in self.WEEKDAYS:
                    for slot in valid_slots:
                        if self.conflict_tracker.are_groups_available(
                            [group], day, slot, WeekType.BOTH
                        ):
                            total_slots += 1

                availability[group] = total_slots

        return availability

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

    def _convert_to_assignments(self, assignments: list[dict]) -> list[Assignment]:
        """Convert assignment dicts to Assignment objects.

        Args:
            assignments: List of assignment dictionaries

        Returns:
            List of Assignment objects
        """
        result = []
        for a in assignments:
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
            result.append(assignment)
        return result

    def _schedule_stream(
        self,
        stream: Stage5PracticalStream,
        subgroup_pairs: dict[str, list[Stage5PracticalStream]],
        scheduled_stream_ids: set[str],
    ) -> list[Assignment] | UnscheduledStream:
        """Schedule a single Stage 5 stream.

        Args:
            stream: Stage5PracticalStream to schedule
            subgroup_pairs: Mapping of subgroup pairs
            scheduled_stream_ids: Set of already scheduled stream IDs

        Returns:
            List of Assignment objects if scheduled,
            or UnscheduledStream with failure reason
        """
        hours = stream.max_hours
        if hours == 0:
            return []

        # Handle subgroup streams specially
        if stream.is_subgroup:
            # For Stage 5, all subgroup pairs have different instructors
            # (critical pairs with same instructor are rare and handled by Stage 3)
            return self._schedule_parallel_subgroup(
                stream, subgroup_pairs, scheduled_stream_ids
            )

        # Non-subgroup stream: standard scheduling
        return self._schedule_non_subgroup(stream)

    def _schedule_non_subgroup(
        self, stream: Stage5PracticalStream, remaining_hours: int | None = None
    ) -> list[Assignment] | UnscheduledStream:
        """Schedule a non-subgroup practical stream.

        Args:
            stream: Stage5PracticalStream to schedule
            remaining_hours: If specified, schedule only this many hours (for split scheduling)

        Returns:
            List of Assignment objects or UnscheduledStream
        """
        hours = remaining_hours if remaining_hours is not None else stream.max_hours
        if hours == 0:
            return []

        position_result = self._find_best_position(stream, hours)

        first_element = position_result[0]
        if isinstance(first_element, Day):
            day, start_slot = position_result
            return self._create_assignments(stream, day, start_slot, hours)
        else:
            reason, details = position_result

            # Try split scheduling: schedule fewer hours, then recurse for remainder
            if hours > 1:
                for partial_hours in range(hours - 1, 0, -1):
                    partial_result = self._find_best_position(stream, partial_hours)
                    if isinstance(partial_result[0], Day):
                        partial_day, partial_slot = partial_result
                        partial_assignments = self._create_assignments(
                            stream, partial_day, partial_slot, partial_hours
                        )
                        if isinstance(partial_assignments, list):
                            # Recursively schedule remaining hours
                            remaining = hours - partial_hours
                            rest_result = self._schedule_non_subgroup(stream, remaining)
                            if isinstance(rest_result, list):
                                return partial_assignments + rest_result
                            # If rest fails, return what we have so far
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

    def _schedule_parallel_subgroup(
        self,
        stream: Stage5PracticalStream,
        subgroup_pairs: dict[str, list[Stage5PracticalStream]],
        scheduled_stream_ids: set[str],
        remaining_hours: int | None = None,
    ) -> list[Assignment] | UnscheduledStream:
        """Schedule a subgroup stream in parallel with its pair.

        For different instructors: both subgroups can run at the same time.
        Students choose which subgroup to attend.

        Args:
            stream: Stage5PracticalStream to schedule
            subgroup_pairs: Mapping of subgroup pairs
            scheduled_stream_ids: Set of already scheduled stream IDs
            remaining_hours: If specified, schedule only this many hours (for split scheduling)

        Returns:
            List of Assignment objects or UnscheduledStream
        """
        hours = remaining_hours if remaining_hours is not None else stream.max_hours
        if hours == 0:
            return []

        # Check if paired stream is already scheduled
        if (
            stream.paired_stream_id
            and stream.paired_stream_id in self._subgroup_schedule
        ):
            # Try to schedule at the same position as paired stream
            paired_day, paired_slot = self._subgroup_schedule[stream.paired_stream_id]
            if self._can_schedule_at(stream, paired_day, paired_slot, hours):
                assignments = self._create_assignments(
                    stream, paired_day, paired_slot, hours
                )
                if isinstance(assignments, list):
                    self._subgroup_schedule[stream.id] = (paired_day, paired_slot)
                    return assignments

        # Find best position (prefer positions where we can schedule both subgroups)
        position_result = self._find_best_position(stream, hours)

        first_element = position_result[0]
        if isinstance(first_element, Day):
            day, start_slot = position_result
            assignments = self._create_assignments(stream, day, start_slot, hours)
            if isinstance(assignments, list):
                self._subgroup_schedule[stream.id] = (day, start_slot)
                return assignments
            return assignments
        else:
            reason, details = position_result

            # Try split scheduling: schedule fewer hours, then recurse for remainder
            if hours > 1:
                for partial_hours in range(hours - 1, 0, -1):
                    partial_result = self._find_best_position(stream, partial_hours)
                    if isinstance(partial_result[0], Day):
                        partial_day, partial_slot = partial_result
                        partial_assignments = self._create_assignments(
                            stream, partial_day, partial_slot, partial_hours
                        )
                        if isinstance(partial_assignments, list):
                            self._subgroup_schedule[stream.id] = (
                                partial_day,
                                partial_slot,
                            )
                            # Recursively schedule remaining hours
                            remaining = hours - partial_hours
                            rest_result = self._schedule_parallel_subgroup(
                                stream, subgroup_pairs, scheduled_stream_ids, remaining
                            )
                            if isinstance(rest_result, list):
                                return partial_assignments + rest_result
                            # If rest fails, return what we have so far
                        break

            return UnscheduledStream(
                stream_id=stream.id,
                subject=stream.subject,
                instructor=stream.instructor,
                groups=stream.groups,
                student_count=stream.student_count,
                shift=stream.shift,
                reason=UnscheduledReason.SUBGROUP_PAIRING_FAILED,
                details=f"Could not find parallel slot: {details}",
            )

    def _find_best_position(
        self, stream: Stage5PracticalStream, hours: int
    ) -> tuple[Day, int] | tuple[UnscheduledReason, str]:
        """Find the best (day, starting_slot) for a stream.

        Strategy:
        PHASE 1: Try days WITHOUT lectures first (soft preference)
        - Sort by group's daily load (prefer days with existing classes)
        - Try gap-filling first, then all slots

        PHASE 2: Try days WITH lectures (fallback)
        - Apply 2-hour subject daily limit

        PHASE 3: Try extended slots (6-7) for first-shift
        - Only when standard slots exhausted

        For 2+ hour streams: Find consecutive available slots

        Args:
            stream: Stage5PracticalStream to schedule
            hours: Number of consecutive hours needed

        Returns:
            Tuple of (Day, start_slot) if position found, or
            Tuple of (UnscheduledReason, details) if no position found
        """
        valid_slots = get_slots_for_shift(stream.shift)

        # For first-shift streams, also consider extended slots (6-7)
        if stream.shift == Shift.FIRST:
            extended_slots = get_slots_for_shift(Shift.FIRST, extended=True)
        else:
            extended_slots = valid_slots

        # Get lecture days for this subject
        lecture_days_set = set(stream.lecture_days)

        # Split days into non-lecture and lecture days
        non_lecture_days = [d for d in self.WEEKDAYS if d not in lecture_days_set]
        lecture_days = [d for d in self.WEEKDAYS if d in lecture_days_set]

        # Sort days by group load (prefer days with existing classes, then least loaded)
        day_loads = {
            day: self.conflict_tracker.get_groups_total_daily_load(stream.groups, day)
            for day in self.WEEKDAYS
        }

        def sort_days_by_load(days: list[Day]) -> list[Day]:
            """Sort days: first those with classes (consolidate), then by load."""
            days_with_classes = [d for d in days if day_loads[d] > 0]
            days_without_classes = [d for d in days if day_loads[d] == 0]
            sorted_with = sorted(days_with_classes, key=lambda d: day_loads[d])
            sorted_without = sorted(days_without_classes, key=lambda d: day_loads[d])
            return sorted_with + sorted_without

        sorted_non_lecture_days = sort_days_by_load(non_lecture_days)
        sorted_lecture_days = sort_days_by_load(lecture_days)

        last_reason: UnscheduledReason | None = None
        last_details: str = ""
        positions_tried = 0

        # PHASE 1: Try non-lecture days first
        for day in sorted_non_lecture_days:
            result = self._try_day(stream, day, hours, valid_slots)
            if result is not None:
                if isinstance(result[0], Day):
                    return result
                positions_tried += 1
                last_reason, last_details = result

        # PHASE 2: Try lecture days (fallback)
        for day in sorted_lecture_days:
            result = self._try_day(stream, day, hours, valid_slots)
            if result is not None:
                if isinstance(result[0], Day):
                    return result
                positions_tried += 1
                last_reason, last_details = result

        # PHASE 3: Try extended slots for first shift
        if stream.shift == Shift.FIRST:
            overflow_slots = [s for s in extended_slots if s not in valid_slots]

            # Try all days with extended slots
            all_sorted_days = sorted_non_lecture_days + sorted_lecture_days

            for day in all_sorted_days:
                for slot in overflow_slots:
                    if hours > 1:
                        consecutive_valid = all(
                            (slot + i) in extended_slots for i in range(hours)
                        )
                        if not consecutive_valid:
                            continue

                    positions_tried += 1
                    passed, reason, details = self._check_all_constraints(
                        stream, day, slot, hours
                    )

                    if passed:
                        return (day, slot)

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

    def _try_day(
        self,
        stream: Stage5PracticalStream,
        day: Day,
        hours: int,
        valid_slots: list[int],
    ) -> tuple[Day, int] | tuple[UnscheduledReason, str] | None:
        """Try to schedule on a specific day.

        Args:
            stream: Stream to schedule
            day: Day to try
            hours: Hours needed
            valid_slots: Valid slots for this shift

        Returns:
            (Day, slot) if successful, (reason, details) if tried but failed, None if not tried
        """
        # Get existing slots for this group to find gaps
        existing_slots = set()
        for group in stream.groups:
            existing_slots.update(
                self.conflict_tracker.get_group_slots_on_day(group, day)
            )

        tried_any = False

        # Try to fill gaps first if group has existing classes
        if existing_slots:
            gap_slots = self._find_gap_slots(list(existing_slots), valid_slots, hours)
            for slot in gap_slots:
                tried_any = True
                if self._passes_all_checks(stream, day, slot, hours):
                    return (day, slot)

        # Then try all other slots in order
        last_reason: UnscheduledReason | None = None
        last_details: str = ""

        for slot in valid_slots:
            if hours > 1:
                consecutive_valid = all((slot + i) in valid_slots for i in range(hours))
                if not consecutive_valid:
                    continue

            tried_any = True
            passed, reason, details = self._check_all_constraints(
                stream, day, slot, hours
            )

            if passed:
                return (day, slot)

            last_reason = reason
            last_details = details

        if tried_any and last_reason:
            return (last_reason, last_details)
        return None

    def _find_gap_slots(
        self, existing_slots: list[int], valid_slots: list[int], hours_needed: int
    ) -> list[int]:
        """Find slots that would fill gaps in existing schedule.

        Args:
            existing_slots: List of slots where group has existing classes
            valid_slots: List of valid slots for this shift
            hours_needed: Number of consecutive hours needed

        Returns:
            List of starting slots that would fill gaps
        """
        if not existing_slots or len(existing_slots) < 2:
            return []

        gap_slots = []
        sorted_existing = sorted(existing_slots)

        # Find gaps between existing classes
        for i in range(len(sorted_existing) - 1):
            start = sorted_existing[i]
            end = sorted_existing[i + 1]

            # Check if there's a gap
            if end - start > 1:
                # Try slots that would fill this gap
                for slot in range(start + 1, end):
                    if slot in valid_slots:
                        # Check if we can fit hours_needed starting here
                        if all(
                            (slot + j) in valid_slots and (slot + j) < end
                            for j in range(hours_needed)
                        ):
                            gap_slots.append(slot)

        return gap_slots

    def _can_schedule_at(
        self, stream: Stage5PracticalStream, day: Day, slot: int, hours: int
    ) -> bool:
        """Check if stream can be scheduled at given position.

        Args:
            stream: Stage5PracticalStream to check
            day: Day of the week
            slot: Starting slot
            hours: Number of hours needed

        Returns:
            True if position is valid
        """
        return self._passes_all_checks(stream, day, slot, hours)

    def _passes_all_checks(
        self, stream: Stage5PracticalStream, day: Day, slot: int, hours: int
    ) -> bool:
        """Check if a position passes all scheduling constraints.

        Args:
            stream: Stream to check
            day: Proposed day
            slot: Proposed starting slot
            hours: Number of consecutive hours

        Returns:
            True if all checks pass
        """
        passed, _, _ = self._check_all_constraints(stream, day, slot, hours)
        return passed

    def _check_all_constraints(
        self, stream: Stage5PracticalStream, day: Day, slot: int, hours: int
    ) -> tuple[bool, UnscheduledReason | None, str]:
        """Check all scheduling constraints for a position.

        Args:
            stream: Stream to check
            day: Proposed day
            slot: Proposed starting slot
            hours: Number of consecutive hours

        Returns:
            Tuple of (passed, reason, details)
        """
        # 1. Subject daily hours (2-hour rule)
        can_normal, can_extreme = self.conflict_tracker.can_add_subject_hours(
            stream.groups, day, stream.subject, hours
        )
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

            # 3a. Building gap slot
            is_gap, gap_group = self.conflict_tracker.is_building_gap_slot(
                stream.groups, day, current_slot
            )
            if is_gap:
                return (
                    False,
                    UnscheduledReason.BUILDING_GAP_REQUIRED,
                    f"Slot {current_slot} is a required travel gap for group '{gap_group}'",
                )

            # 3b. Max windows check
            would_create, window_group = (
                self.conflict_tracker.would_create_second_window(
                    stream.groups, day, current_slot
                )
            )
            if would_create:
                return (
                    False,
                    UnscheduledReason.MAX_WINDOWS_EXCEEDED,
                    f"Group '{window_group}' would have too many windows on {day.value}",
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

            # 3d. Building gap constraint
            current_room = self.room_manager.find_room_for_stage5(
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

        # 5. Room availability
        room = self.room_manager.find_room_for_stage5(stream, day, slot)
        if not room:
            return (
                False,
                UnscheduledReason.NO_ROOM_AVAILABLE,
                f"No room with capacity >= {stream.student_count} on {day.value} slot {slot}",
            )

        return (True, None, "")

    def _create_assignments(
        self,
        stream: Stage5PracticalStream,
        day: Day,
        start_slot: int,
        hours: int,
    ) -> list[Assignment] | UnscheduledStream:
        """Create assignments for consecutive hours on a single day.

        Args:
            stream: Stage5PracticalStream to schedule
            day: Day to schedule on
            start_slot: Starting slot number
            hours: Number of consecutive hours to schedule

        Returns:
            List of Assignment objects if successful,
            or UnscheduledStream if room allocation fails
        """
        assignments = []
        rooms: list[Room] = []
        preferred_room: Room | None = None

        # Find rooms for all consecutive slots
        for i in range(hours):
            slot = start_slot + i

            if preferred_room and self.room_manager.is_room_available(
                preferred_room.name, day, slot, WeekType.BOTH
            ):
                room = preferred_room
            else:
                room = self.room_manager.find_room_for_stage5(stream, day, slot)

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

    def _compute_statistics(
        self,
        assignments: list[Assignment],
        expected_hours: int = 0,
        scheduled_hours: int = 0,
    ) -> ScheduleStatistics:
        """Compute statistics for the generated schedule.

        Args:
            assignments: List of Assignment objects
            expected_hours: Total hours expected to be scheduled at this stage
            scheduled_hours: Total hours actually scheduled at this stage

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
            expected_hours=expected_hours,
            scheduled_hours=scheduled_hours,
        )


def create_stage5_scheduler(
    rooms_csv: Path | str,
    subject_rooms_json: Path | str | None = None,
    instructor_rooms_json: Path | str | None = None,
    group_buildings_json: Path | str | None = None,
    instructor_availability_json: Path | str | None = None,
    nearby_buildings_json: Path | str | None = None,
    instructor_days_json: Path | str | None = None,
    groups_second_shift_csv: Path | str | None = None,
) -> Stage5Scheduler:
    """Factory function to create a Stage5Scheduler with loaded reference data.

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
        Configured Stage5Scheduler instance
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

    return Stage5Scheduler(
        rooms_path,
        subject_rooms,
        instructor_rooms,
        group_buildings,
        instructor_availability,
        nearby_buildings,
        instructor_day_constraints,
        second_shift_groups,
    )
