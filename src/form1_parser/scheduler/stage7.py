"""Stage 7 scheduler: Schedule optimization.

Stage 7 optimizes the schedule through two phases:
- Phase 7A: Redistribute assignments to fill empty group-days
- Phase 7B: Attempt to schedule previously unscheduled streams
"""

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .conflicts import ConflictTracker
from .constants import (
    Shift,
    get_slots_for_shift,
)
from .models import (
    Assignment,
    Day,
    Room,
    ScheduleResult,
    ScheduleStatistics,
    UnscheduledReason,
    UnscheduledStream,
    WeekType,
)
from .rooms import RoomManager
from .utils import (
    clean_instructor_name,
    load_second_shift_groups,
    parse_group_year,
    parse_subgroup_info,
)


@dataclass
class GroupDayAnalysis:
    """Analysis of a group's schedule for a specific day."""

    group: str
    day: Day
    slot_count: int
    slots: list[int]
    is_empty: bool
    is_overloaded: bool  # 6+ lessons


@dataclass
class MovableAssignment:
    """An assignment that can potentially be moved."""

    assignment: Assignment
    source_day: Day
    source_slot: int
    target_day: Day
    target_slot: int
    target_room: Room | None = None
    move_score: float = 0.0  # Higher = better move


@dataclass
class Phase7AMetrics:
    """Metrics for Phase 7A (empty day correction)."""

    groups_with_empty_days_before: int = 0
    groups_with_empty_days_after: int = 0
    total_empty_group_days_before: int = 0
    total_empty_group_days_after: int = 0
    assignments_moved: int = 0
    iterations: int = 0


@dataclass
class Phase7BMetrics:
    """Metrics for Phase 7B (rescheduling unscheduled streams)."""

    unscheduled_before: int = 0
    unscheduled_after: int = 0
    newly_scheduled: int = 0
    by_original_reason: dict[str, dict[str, int]] = field(default_factory=dict)


class Stage7Scheduler:
    """Stage 7 scheduler for schedule optimization.

    Phase 7A: Redistribute assignments to fill empty group-days
    Phase 7B: Attempt to schedule previously unscheduled streams
    """

    # Working days for scheduling
    WORKING_DAYS = [
        Day.MONDAY,
        Day.TUESDAY,
        Day.WEDNESDAY,
        Day.THURSDAY,
        Day.FRIDAY,
    ]

    # Maximum daily load for a group
    MAX_DAILY_LOAD = 6

    # Maximum iterations for Phase 7A
    MAX_PHASE7A_ITERATIONS = 100

    # Maximum windows allowed per day
    MAX_WINDOWS = 3

    def __init__(
        self,
        room_manager: RoomManager,
        conflict_tracker: ConflictTracker,
        instructor_availability: list[dict] | None = None,
        second_shift_groups: set[str] | None = None,
    ) -> None:
        """Initialize the Stage 7 scheduler.

        Args:
            room_manager: RoomManager instance for room allocation
            conflict_tracker: ConflictTracker for conflict detection
            instructor_availability: List of instructor availability records
            second_shift_groups: Set of groups that require second shift
        """
        self.room_manager = room_manager
        self.conflict_tracker = conflict_tracker
        self.instructor_availability = instructor_availability or []
        self.second_shift_groups = second_shift_groups or set()

        # Build instructor availability lookup
        self._instructor_unavailable = self._build_instructor_unavailable_lookup()

        # Track base groups for subgroup detection
        self._subgroup_streams: set[str] = set()

    def _build_instructor_unavailable_lookup(self) -> dict[str, dict[str, set[str]]]:
        """Build lookup for instructor unavailability.

        Returns:
            Dict mapping instructor name -> {day: set(times)}
        """
        lookup: dict[str, dict[str, set[str]]] = {}
        for record in self.instructor_availability:
            name = record.get("name", "")
            if not name:
                continue
            weekly = record.get("weekly_unavailable", {})
            if weekly:
                lookup[name] = {day: set(times) for day, times in weekly.items()}
        return lookup

    def schedule(
        self,
        streams: list[dict],
        previous_assignments: list[dict],
        previous_unscheduled: list[dict],
    ) -> ScheduleResult:
        """Run Stage 7 optimization.

        Args:
            streams: List of all stream dictionaries from parsed JSON
            previous_assignments: List of assignment dicts from Stage 6
            previous_unscheduled: List of unscheduled stream dicts from Stage 6

        Returns:
            ScheduleResult with optimized schedule
        """
        # Convert previous assignments to Assignment objects
        assignments = self._load_assignments(previous_assignments)

        # Load assignments into trackers
        self._load_into_trackers(previous_assignments)

        # Identify subgroup streams
        self._identify_subgroup_streams(streams)

        # Run Phase 7A: Empty day correction
        phase7a_metrics = self._run_phase_7a(assignments)

        # Run Phase 7B: Reschedule unscheduled streams
        phase7b_metrics, newly_scheduled = self._run_phase_7b(
            streams, previous_unscheduled, assignments
        )

        # Build final unscheduled list
        final_unscheduled = self._build_final_unscheduled(
            previous_unscheduled, newly_scheduled
        )

        # Build statistics
        statistics = self._build_statistics(
            assignments, phase7a_metrics, phase7b_metrics
        )

        return ScheduleResult(
            generation_date=datetime.now().isoformat(),
            stage=7,
            assignments=assignments,
            unscheduled_stream_ids=[u.stream_id for u in final_unscheduled],
            unscheduled_streams=final_unscheduled,
            statistics=statistics,
        )

    def _load_assignments(self, assignment_dicts: list[dict]) -> list[Assignment]:
        """Convert assignment dictionaries to Assignment objects.

        Args:
            assignment_dicts: List of assignment dictionaries

        Returns:
            List of Assignment objects
        """
        assignments = []
        for a in assignment_dicts:
            assignment = Assignment(
                stream_id=a.get("stream_id", ""),
                subject=a.get("subject", ""),
                instructor=a.get("instructor", ""),
                groups=a.get("groups", []),
                student_count=a.get("student_count", 0),
                day=Day(a.get("day", "monday")),
                slot=a.get("slot", 1),
                room=a.get("room", ""),
                room_address=a.get("room_address", ""),
                week_type=WeekType(a.get("week_type", "both")),
                stream_type=a.get("stream_type", "lecture"),
            )
            assignments.append(assignment)
        return assignments

    def _load_into_trackers(self, assignment_dicts: list[dict]) -> None:
        """Load assignments into conflict tracker and room manager.

        Args:
            assignment_dicts: List of assignment dictionaries
        """
        for a in assignment_dicts:
            day = Day(a.get("day", "monday"))
            slot = a.get("slot", 1)
            instructor = a.get("instructor", "")
            groups = a.get("groups", [])
            room_name = a.get("room", "")
            room_address = a.get("room_address", "")
            week_type = WeekType(a.get("week_type", "both"))
            subject = a.get("subject", "")

            # Reserve in conflict tracker
            self.conflict_tracker.reserve(
                instructor, groups, day, slot, week_type, building_address=room_address
            )

            # Track subject hours
            self.conflict_tracker.reserve_subject_hours(groups, day, subject, 1)

            # Reserve room
            room = self.room_manager.get_room_by_name(room_name, room_address)
            if room:
                self.room_manager.reserve_room(room, day, slot, week_type)

    def _identify_subgroup_streams(self, streams: list[dict]) -> None:
        """Identify which stream IDs are subgroup streams.

        Args:
            streams: List of all stream dictionaries
        """
        for stream in streams:
            stream_id = stream.get("id", "")
            groups = stream.get("groups", [])

            # Check if any group has subgroup notation
            for group in groups:
                _, subgroup_num = parse_subgroup_info(group)
                if subgroup_num is not None:
                    self._subgroup_streams.add(stream_id)
                    break

            # Also check is_subgroup and is_implicit_subgroup flags
            if stream.get("is_subgroup", False) or stream.get(
                "is_implicit_subgroup", False
            ):
                self._subgroup_streams.add(stream_id)

    # =============================
    # Phase 7A: Empty Day Correction
    # =============================

    def _run_phase_7a(self, assignments: list[Assignment]) -> Phase7AMetrics:
        """Run Phase 7A: Redistribute to fill empty group-days.

        Args:
            assignments: List of Assignment objects (modified in place)

        Returns:
            Phase7AMetrics with results
        """
        metrics = Phase7AMetrics()

        # Analyze initial state
        initial_analysis = self._analyze_group_schedules(assignments)
        metrics.groups_with_empty_days_before = self._count_groups_with_empty_days(
            initial_analysis
        )
        metrics.total_empty_group_days_before = self._count_total_empty_days(
            initial_analysis
        )

        # Iterative improvement
        for iteration in range(self.MAX_PHASE7A_ITERATIONS):
            metrics.iterations = iteration + 1

            # Find groups with empty days
            analysis = self._analyze_group_schedules(assignments)
            groups_with_empty = [
                (group, data)
                for group, data in analysis.items()
                if self._has_empty_days(data)
            ]

            if not groups_with_empty:
                break

            # Try to fix one empty day
            moved = False
            for group, day_data in groups_with_empty:
                empty_days = [d for d, info in day_data.items() if info.is_empty]
                overloaded_days = [
                    d for d, info in day_data.items() if info.is_overloaded
                ]

                if not empty_days:
                    continue

                # Find a movable assignment
                movable = self._find_movable_assignment(
                    group, empty_days, overloaded_days, assignments
                )

                if movable:
                    success = self._execute_move(movable, assignments)
                    if success:
                        metrics.assignments_moved += 1
                        moved = True
                        break

            # If no improvement possible, stop
            if not moved:
                break

        # Analyze final state
        final_analysis = self._analyze_group_schedules(assignments)
        metrics.groups_with_empty_days_after = self._count_groups_with_empty_days(
            final_analysis
        )
        metrics.total_empty_group_days_after = self._count_total_empty_days(
            final_analysis
        )

        return metrics

    def _analyze_group_schedules(
        self, assignments: list[Assignment]
    ) -> dict[str, dict[Day, GroupDayAnalysis]]:
        """Analyze all groups' schedules to find empty and overloaded days.

        Args:
            assignments: List of Assignment objects

        Returns:
            Dict mapping base_group -> {day: GroupDayAnalysis}
        """
        # Collect slots per group per day
        group_day_slots: dict[str, dict[Day, list[int]]] = defaultdict(
            lambda: defaultdict(list)
        )

        for assignment in assignments:
            for group in assignment.groups:
                # Get base group (strip subgroup suffix)
                base_group, _ = parse_subgroup_info(group)
                group_day_slots[base_group][assignment.day].append(assignment.slot)

        # Build analysis
        analysis: dict[str, dict[Day, GroupDayAnalysis]] = {}

        for base_group, day_slots in group_day_slots.items():
            analysis[base_group] = {}
            for day in self.WORKING_DAYS:
                slots = sorted(set(day_slots.get(day, [])))
                slot_count = len(slots)
                analysis[base_group][day] = GroupDayAnalysis(
                    group=base_group,
                    day=day,
                    slot_count=slot_count,
                    slots=slots,
                    is_empty=slot_count == 0,
                    is_overloaded=slot_count >= self.MAX_DAILY_LOAD,
                )

        return analysis

    def _has_empty_days(self, day_data: dict[Day, GroupDayAnalysis]) -> bool:
        """Check if a group has any empty weekdays."""
        return any(info.is_empty for info in day_data.values())

    def _count_groups_with_empty_days(
        self, analysis: dict[str, dict[Day, GroupDayAnalysis]]
    ) -> int:
        """Count groups that have at least one empty day."""
        return sum(
            1 for day_data in analysis.values() if self._has_empty_days(day_data)
        )

    def _count_total_empty_days(
        self, analysis: dict[str, dict[Day, GroupDayAnalysis]]
    ) -> int:
        """Count total empty group-days across all groups."""
        total = 0
        for day_data in analysis.values():
            total += sum(1 for info in day_data.values() if info.is_empty)
        return total

    def _find_movable_assignment(
        self,
        group: str,
        empty_days: list[Day],
        overloaded_days: list[Day],
        assignments: list[Assignment],
    ) -> MovableAssignment | None:
        """Find an assignment that can be moved to fill an empty day.

        Args:
            group: Base group name with empty day
            empty_days: List of days with no classes
            overloaded_days: List of days with 6+ classes
            assignments: All assignments

        Returns:
            MovableAssignment if found, None otherwise
        """
        # Prioritize moving from overloaded days
        source_days = overloaded_days if overloaded_days else self.WORKING_DAYS

        candidates: list[MovableAssignment] = []

        for assignment in assignments:
            # Skip if group not in this assignment
            base_groups = [parse_subgroup_info(g)[0] for g in assignment.groups]
            if group not in base_groups:
                continue

            # Skip if not from a source day
            if assignment.day not in source_days:
                continue

            # Skip subgroup assignments (preserve pairing)
            if assignment.stream_id in self._subgroup_streams:
                continue

            # Skip multi-group streams where other groups might conflict
            if len(assignment.groups) > 1:
                # More complex validation needed for multi-group
                continue

            # Try to move to each empty day
            for target_day in empty_days:
                movable = self._validate_move(assignment, target_day, assignments)
                if movable:
                    candidates.append(movable)

        if not candidates:
            return None

        # Return the best candidate (highest move score)
        return max(candidates, key=lambda m: m.move_score)

    def _validate_move(
        self,
        assignment: Assignment,
        target_day: Day,
        assignments: list[Assignment],
    ) -> MovableAssignment | None:
        """Validate if an assignment can be moved to a target day.

        Args:
            assignment: Assignment to validate
            target_day: Day to move to
            assignments: All assignments

        Returns:
            MovableAssignment if valid, None otherwise
        """
        instructor = assignment.instructor
        groups = assignment.groups
        week_type = assignment.week_type

        # Determine shift for this assignment
        year = parse_group_year(groups[0]) if groups else 1
        shift = Shift.SECOND if year == 2 else Shift.FIRST
        if groups and groups[0] in self.second_shift_groups:
            shift = Shift.SECOND

        shift_slots = get_slots_for_shift(shift)

        # Try each slot in the shift
        for target_slot in shift_slots:
            # Check instructor availability (weekly unavailability)
            cleaned_name = clean_instructor_name(instructor)
            if cleaned_name in self._instructor_unavailable:
                day_unavail = self._instructor_unavailable[cleaned_name].get(
                    target_day.value, set()
                )
                # Check if slot time is in unavailable times
                from .constants import get_slot_start_time

                slot_time = get_slot_start_time(target_slot)
                if slot_time and slot_time in day_unavail:
                    continue

            # Temporarily release the current slot
            self.conflict_tracker.release_slot(
                instructor,
                groups,
                assignment.day,
                assignment.slot,
                week_type,
                assignment.room_address,
            )
            self.conflict_tracker.release_subject_hours(
                groups, assignment.day, assignment.subject, 1
            )
            room = self.room_manager.get_room_by_name(
                assignment.room, assignment.room_address
            )
            if room:
                self.room_manager.release_room(
                    assignment.room, assignment.day, assignment.slot, week_type
                )

            # Check if target slot is available
            is_available, reason, _ = (
                self.conflict_tracker.check_slot_availability_reason(
                    instructor, groups, target_day, target_slot, week_type
                )
            )
            if not is_available:
                # Re-reserve the original slot before continuing
                self._restore_original_slot(
                    instructor, groups, assignment, room, week_type
                )
                continue

            # Check daily load constraint
            load_ok = True
            for g in groups:
                current_load = self.conflict_tracker.get_group_daily_load(g, target_day)
                if current_load >= self.MAX_DAILY_LOAD:
                    load_ok = False
                    break
            if not load_ok:
                self._restore_original_slot(
                    instructor, groups, assignment, room, week_type
                )
                continue

            # Check subject daily limit
            can_normal, _ = self.conflict_tracker.can_add_subject_hours(
                groups, target_day, assignment.subject, 1
            )
            if not can_normal:
                self._restore_original_slot(
                    instructor, groups, assignment, room, week_type
                )
                continue

            # Check windows constraint
            would_exceed, _ = self.conflict_tracker.would_create_second_window(
                groups, target_day, target_slot, week_type, self.MAX_WINDOWS
            )
            if would_exceed:
                self._restore_original_slot(
                    instructor, groups, assignment, room, week_type
                )
                continue

            # Find a proper room respecting subject-room constraints
            room_available = self._find_room_for_assignment(
                assignment, target_day, target_slot, week_type
            )
            if not room_available:
                self._restore_original_slot(
                    instructor, groups, assignment, room, week_type
                )
                continue

            # Check building gap constraint using the NEW room's address
            building_ok, _, _ = self.conflict_tracker.check_building_gap_constraint(
                groups, target_day, target_slot, room_available.address, week_type
            )
            if not building_ok:
                self._restore_original_slot(
                    instructor, groups, assignment, room, week_type
                )
                continue

            # All checks passed! Re-reserve the original slot and return the movable
            self._restore_original_slot(instructor, groups, assignment, room, week_type)

            # Calculate move score (higher = better)
            move_score = 100.0
            # Bonus for moving from overloaded day
            source_load = sum(
                self.conflict_tracker.get_group_daily_load(g, assignment.day)
                for g in groups
            )
            if source_load >= self.MAX_DAILY_LOAD:
                move_score += 50.0

            return MovableAssignment(
                assignment=assignment,
                source_day=assignment.day,
                source_slot=assignment.slot,
                target_day=target_day,
                target_slot=target_slot,
                target_room=room_available,
                move_score=move_score,
            )

        return None

    def _restore_original_slot(
        self,
        instructor: str,
        groups: list[str],
        assignment: Assignment,
        room: Room | None,
        week_type: WeekType,
    ) -> None:
        """Restore the original slot reservation after validation.

        Args:
            instructor: Instructor name
            groups: List of group names
            assignment: Original assignment
            room: Room object (or None)
            week_type: Week type
        """
        self.conflict_tracker.reserve(
            instructor,
            groups,
            assignment.day,
            assignment.slot,
            week_type,
            assignment.room_address,
        )
        self.conflict_tracker.reserve_subject_hours(
            groups, assignment.day, assignment.subject, 1
        )
        if room:
            self.room_manager.reserve_room(
                room, assignment.day, assignment.slot, week_type
            )

    def _execute_move(
        self,
        movable: MovableAssignment,
        assignments: list[Assignment],
    ) -> bool:
        """Execute a validated move.

        Args:
            movable: MovableAssignment with validated move details
            assignments: List of all assignments (modified in place)

        Returns:
            True if move was successful
        """
        assignment = movable.assignment
        instructor = assignment.instructor
        groups = assignment.groups
        week_type = assignment.week_type

        # Release old slot
        self.conflict_tracker.release_slot(
            instructor,
            groups,
            movable.source_day,
            movable.source_slot,
            week_type,
            assignment.room_address,
        )
        self.conflict_tracker.release_subject_hours(
            groups, movable.source_day, assignment.subject, 1
        )
        old_room = self.room_manager.get_room_by_name(
            assignment.room, assignment.room_address
        )
        if old_room:
            self.room_manager.release_room(
                assignment.room, movable.source_day, movable.source_slot, week_type
            )

        # Reserve new slot
        new_room = movable.target_room
        new_address = new_room.address if new_room else assignment.room_address

        self.conflict_tracker.reserve(
            instructor,
            groups,
            movable.target_day,
            movable.target_slot,
            week_type,
            new_address,
        )
        self.conflict_tracker.reserve_subject_hours(
            groups, movable.target_day, assignment.subject, 1
        )
        if new_room:
            self.room_manager.reserve_room(
                new_room, movable.target_day, movable.target_slot, week_type
            )

        # Update assignment object
        assignment.day = movable.target_day
        assignment.slot = movable.target_slot
        if new_room:
            assignment.room = new_room.name
            assignment.room_address = new_room.address

        return True

    # =====================================
    # Phase 7B: Reschedule Unscheduled
    # =====================================

    def _run_phase_7b(
        self,
        streams: list[dict],
        previous_unscheduled: list[dict],
        assignments: list[Assignment],
    ) -> tuple[Phase7BMetrics, set[str]]:
        """Run Phase 7B: Attempt to schedule previously unscheduled streams.

        Args:
            streams: List of all stream dictionaries
            previous_unscheduled: List of unscheduled stream dicts from Stage 6
            assignments: List of Assignment objects (modified in place)

        Returns:
            Tuple of (Phase7BMetrics, set of newly scheduled stream IDs)
        """
        metrics = Phase7BMetrics()
        metrics.unscheduled_before = len(previous_unscheduled)
        metrics.by_original_reason = defaultdict(lambda: {"before": 0, "after": 0})

        newly_scheduled: set[str] = set()

        # Build stream lookup
        stream_lookup = {s.get("id", ""): s for s in streams}

        # Sort unscheduled by priority (most constrained first)
        sorted_unscheduled = self._sort_unscheduled_by_priority(previous_unscheduled)

        for unscheduled_dict in sorted_unscheduled:
            stream_id = unscheduled_dict.get("stream_id", "")
            reason = unscheduled_dict.get("reason", "")
            metrics.by_original_reason[reason]["before"] += 1

            # Get stream details
            stream = stream_lookup.get(stream_id)
            if not stream:
                continue

            # Try to schedule
            assignment = self._try_schedule_stream(stream, reason)
            if assignment:
                assignments.append(assignment)
                newly_scheduled.add(stream_id)
                metrics.newly_scheduled += 1
            else:
                metrics.by_original_reason[reason]["after"] += 1

        metrics.unscheduled_after = metrics.unscheduled_before - metrics.newly_scheduled
        return metrics, newly_scheduled

    def _sort_unscheduled_by_priority(self, unscheduled: list[dict]) -> list[dict]:
        """Sort unscheduled streams by priority (most constrained first).

        Args:
            unscheduled: List of unscheduled stream dicts

        Returns:
            Sorted list
        """
        # Priority order by reason
        reason_priority = {
            "building_gap_required": 1,
            "subject_daily_limit_exceeded": 2,
            "group_conflict": 3,
            "instructor_conflict": 4,
            "no_room_available": 5,
            "all_slots_exhausted": 6,
            "instructor_unavailable": 7,
            "daily_load_exceeded": 8,
            "max_windows_exceeded": 9,
            "subgroup_pairing_failed": 10,
        }

        return sorted(
            unscheduled,
            key=lambda u: reason_priority.get(u.get("reason", ""), 100),
        )

    def _try_schedule_stream(
        self, stream: dict, original_reason: str
    ) -> Assignment | None:
        """Attempt to schedule a previously unscheduled stream.

        Args:
            stream: Stream dictionary
            original_reason: Original failure reason

        Returns:
            Assignment if successful, None otherwise
        """
        stream_id = stream.get("id", "")
        subject = stream.get("subject", "")
        instructor = stream.get("instructor", "")
        groups = stream.get("groups", [])
        student_count = stream.get("student_count", 0)
        stream_type = stream.get("stream_type", "practical")

        if not groups:
            return None

        # Determine shift
        year = parse_group_year(groups[0])
        shift = Shift.SECOND if year == 2 else Shift.FIRST
        if groups[0] in self.second_shift_groups:
            shift = Shift.SECOND

        hours = stream.get("hours", {})
        odd_week = hours.get("odd_week", 0)
        even_week = hours.get("even_week", 0)

        # Determine week type
        if odd_week > 0 and even_week > 0:
            week_type = WeekType.BOTH
        elif odd_week > 0:
            week_type = WeekType.ODD
        elif even_week > 0:
            week_type = WeekType.EVEN
        else:
            return None

        shift_slots = get_slots_for_shift(shift)

        # Strategy based on original reason
        days_to_try = self._get_days_for_strategy(original_reason, groups)

        for day in days_to_try:
            for slot in shift_slots:
                # Check slot availability
                is_available, reason, _ = (
                    self.conflict_tracker.check_slot_availability_reason(
                        instructor, groups, day, slot, week_type
                    )
                )
                if not is_available:
                    continue

                # Check daily load
                load_exceeded, _ = self.conflict_tracker.would_exceed_daily_load(
                    groups, day, 1, self.MAX_DAILY_LOAD, week_type
                )
                if load_exceeded:
                    continue

                # Check subject daily limit
                can_normal, _ = self.conflict_tracker.can_add_subject_hours(
                    groups, day, subject, 1
                )
                if not can_normal:
                    continue

                # Check windows
                would_exceed, _ = self.conflict_tracker.would_create_second_window(
                    groups, day, slot, week_type, self.MAX_WINDOWS
                )
                if would_exceed:
                    continue

                # Find room
                room = self._find_room_for_stream(
                    stream, day, slot, week_type, stream_type
                )
                if not room:
                    continue

                # Check building gap
                building_ok, _, _ = self.conflict_tracker.check_building_gap_constraint(
                    groups, day, slot, room.address, week_type
                )
                if not building_ok:
                    continue

                # Success - create assignment
                self.conflict_tracker.reserve(
                    instructor, groups, day, slot, week_type, room.address
                )
                self.conflict_tracker.reserve_subject_hours(groups, day, subject, 1)
                self.room_manager.reserve_room(room, day, slot, week_type)

                return Assignment(
                    stream_id=stream_id,
                    subject=subject,
                    instructor=instructor,
                    groups=groups,
                    student_count=student_count,
                    day=day,
                    slot=slot,
                    room=room.name,
                    room_address=room.address,
                    week_type=week_type,
                    stream_type=stream_type,
                )

        return None

    def _get_days_for_strategy(
        self, original_reason: str, groups: list[str]
    ) -> list[Day]:
        """Get days to try based on original failure reason.

        Args:
            original_reason: Original failure reason
            groups: List of group names

        Returns:
            List of days to try
        """
        if original_reason == "subject_daily_limit_exceeded":
            # Try different days than where the subject is already scheduled
            # For simplicity, try all days in reverse order (less common days first)
            return list(reversed(self.WORKING_DAYS))
        elif original_reason in ("all_slots_exhausted", "no_room_available"):
            # After Phase 7A freed up some slots, try all days
            return self.WORKING_DAYS
        else:
            # Default: try all working days
            return self.WORKING_DAYS

    def _find_room_for_assignment(
        self,
        assignment: Assignment,
        day: Day,
        slot: int,
        week_type: WeekType,
    ) -> Room | None:
        """Find a room for an assignment respecting subject-room constraints.

        Args:
            assignment: Assignment to find room for
            day: Day to schedule on
            slot: Slot to schedule at
            week_type: Week type

        Returns:
            Room if found, None otherwise
        """
        subject = assignment.subject
        instructor = assignment.instructor
        groups = assignment.groups
        student_count = assignment.student_count
        stream_type = assignment.stream_type

        # 0. Instructor special rooms (highest priority)
        clean_name = self.room_manager._clean_instructor_name(instructor)
        special_rooms = self.room_manager._get_instructor_special_rooms(
            clean_name, stream_type
        )
        if special_rooms:
            room = self.room_manager._find_available_by_capacity(
                special_rooms, student_count, day, slot, week_type, allow_special=True
            )
            if room:
                return room

        # 1. Check if subject has required rooms (subject-rooms.json)
        if subject in self.room_manager.subject_rooms:
            allowed = self.room_manager._get_subject_rooms(subject, stream_type)
            if allowed:
                # Check if any of these rooms are special
                has_special = any(r.is_special for r in allowed)

                room = self.room_manager._find_available_by_capacity(
                    allowed, student_count, day, slot, week_type, allow_special=True
                )
                if room:
                    return room

                # If subject requires special rooms, don't fall back to general pool
                if has_special:
                    return None

        # 2. Try instructor non-special rooms
        if clean_name in self.room_manager.instructor_rooms:
            allowed = self.room_manager._get_instructor_rooms(clean_name, stream_type)
            if allowed:
                has_special = any(r.is_special for r in allowed)
                room = self.room_manager._find_available_by_capacity(
                    allowed, student_count, day, slot, week_type, allow_special=True
                )
                if room:
                    return room
                # If instructor requires special rooms, don't fall back
                if has_special:
                    return None

        # 3. Try group building preferences
        preferred = self.room_manager._get_group_building_rooms(groups)
        if preferred:
            room = self.room_manager._find_available_by_capacity(
                preferred, student_count, day, slot, week_type, allow_special=False
            )
            if room:
                return room

        # 4. General pool (only if no special requirements)
        return self.room_manager._find_available_by_capacity(
            self.room_manager.rooms,
            student_count,
            day,
            slot,
            week_type,
            allow_special=False,
            groups=groups,
        )

    def _find_room_for_stream(
        self,
        stream: dict,
        day: Day,
        slot: int,
        week_type: WeekType,
        stream_type: str,
    ) -> Room | None:
        """Find a room for a stream respecting subject-room constraints.

        Args:
            stream: Stream dictionary
            day: Day to schedule on
            slot: Slot to schedule at
            week_type: Week type
            stream_type: Type of stream (lecture, practical, lab)

        Returns:
            Room if found, None otherwise
        """
        student_count = stream.get("student_count", 0)
        groups = stream.get("groups", [])
        subject = stream.get("subject", "")
        instructor = stream.get("instructor", "")

        # 0. Instructor special rooms (highest priority)
        clean_name = self.room_manager._clean_instructor_name(instructor)
        special_rooms = self.room_manager._get_instructor_special_rooms(
            clean_name, stream_type
        )
        if special_rooms:
            room = self.room_manager._find_available_by_capacity(
                special_rooms, student_count, day, slot, week_type, allow_special=True
            )
            if room:
                return room

        # 1. Check if subject has required rooms (subject-rooms.json)
        if subject in self.room_manager.subject_rooms:
            allowed = self.room_manager._get_subject_rooms(subject, stream_type)
            if allowed:
                # Check if any of these rooms are special
                has_special = any(r.is_special for r in allowed)

                room = self.room_manager._find_available_by_capacity(
                    allowed, student_count, day, slot, week_type, allow_special=True
                )
                if room:
                    return room

                # If subject requires special rooms, don't fall back to general pool
                if has_special:
                    return None

        # 2. Try instructor non-special rooms
        if clean_name in self.room_manager.instructor_rooms:
            allowed = self.room_manager._get_instructor_rooms(clean_name, stream_type)
            if allowed:
                has_special = any(r.is_special for r in allowed)
                room = self.room_manager._find_available_by_capacity(
                    allowed, student_count, day, slot, week_type, allow_special=True
                )
                if room:
                    return room
                # If instructor requires special rooms, don't fall back
                if has_special:
                    return None

        # 3. Try group building preferences
        preferred = self.room_manager._get_group_building_rooms(groups)
        if preferred:
            room = self.room_manager._find_available_by_capacity(
                preferred, student_count, day, slot, week_type, allow_special=False
            )
            if room:
                return room

        # 4. General pool (only if no special requirements)
        return self.room_manager._find_available_by_capacity(
            self.room_manager.rooms,
            student_count,
            day,
            slot,
            week_type,
            allow_special=False,
            groups=groups,
        )

    def _build_final_unscheduled(
        self,
        previous_unscheduled: list[dict],
        newly_scheduled: set[str],
    ) -> list[UnscheduledStream]:
        """Build final list of unscheduled streams.

        Args:
            previous_unscheduled: List of unscheduled dicts from previous stage
            newly_scheduled: Set of stream IDs that were scheduled in Phase 7B

        Returns:
            List of UnscheduledStream objects
        """
        result = []
        for u in previous_unscheduled:
            stream_id = u.get("stream_id", "")
            if stream_id in newly_scheduled:
                continue

            result.append(
                UnscheduledStream(
                    stream_id=stream_id,
                    subject=u.get("subject", ""),
                    instructor=u.get("instructor", ""),
                    groups=u.get("groups", []),
                    student_count=u.get("student_count", 0),
                    shift=Shift(u.get("shift", "first")),
                    reason=UnscheduledReason(u.get("reason", "all_slots_exhausted")),
                    details=u.get("details", ""),
                )
            )
        return result

    def _build_statistics(
        self,
        assignments: list[Assignment],
        phase7a_metrics: Phase7AMetrics,
        phase7b_metrics: Phase7BMetrics,
    ) -> ScheduleStatistics:
        """Build statistics for the schedule result.

        Args:
            assignments: Final list of assignments
            phase7a_metrics: Metrics from Phase 7A
            phase7b_metrics: Metrics from Phase 7B

        Returns:
            ScheduleStatistics object
        """
        stats = ScheduleStatistics()

        # By day
        for assignment in assignments:
            day = assignment.day.value
            stats.by_day[day] = stats.by_day.get(day, 0) + 1

        # By shift
        for assignment in assignments:
            year = parse_group_year(assignment.groups[0]) if assignment.groups else 1
            shift = "second" if year == 2 else "first"
            stats.by_shift[shift] = stats.by_shift.get(shift, 0) + 1

        # Room utilization by address
        for assignment in assignments:
            addr = assignment.room_address
            stats.room_utilization[addr] = stats.room_utilization.get(addr, 0) + 1

        # Expected vs scheduled hours (based on Phase 7B)
        stats.expected_hours = phase7b_metrics.unscheduled_before
        stats.scheduled_hours = phase7b_metrics.newly_scheduled

        return stats


def create_stage7_scheduler(
    rooms_csv: Path,
    subject_rooms_path: Path | None = None,
    instructor_rooms_path: Path | None = None,
    group_buildings_path: Path | None = None,
    instructor_availability_path: Path | None = None,
    nearby_buildings_path: Path | None = None,
    instructor_days_path: Path | None = None,
    groups_second_shift_path: Path | None = None,
) -> Stage7Scheduler:
    """Create a Stage 7 scheduler with all dependencies.

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
        Configured Stage7Scheduler instance
    """
    # Load JSON files
    subject_rooms = None
    if subject_rooms_path and subject_rooms_path.exists():
        with open(subject_rooms_path, encoding="utf-8") as f:
            subject_rooms = json.load(f)

    instructor_rooms = None
    if instructor_rooms_path and instructor_rooms_path.exists():
        with open(instructor_rooms_path, encoding="utf-8") as f:
            instructor_rooms = json.load(f)

    group_buildings = None
    if group_buildings_path and group_buildings_path.exists():
        with open(group_buildings_path, encoding="utf-8") as f:
            group_buildings = json.load(f)

    instructor_availability = None
    if instructor_availability_path and instructor_availability_path.exists():
        with open(instructor_availability_path, encoding="utf-8") as f:
            instructor_availability = json.load(f)

    nearby_buildings = None
    if nearby_buildings_path and nearby_buildings_path.exists():
        with open(nearby_buildings_path, encoding="utf-8") as f:
            nearby_buildings = json.load(f)

    instructor_days = None
    if instructor_days_path and instructor_days_path.exists():
        with open(instructor_days_path, encoding="utf-8") as f:
            instructor_days = json.load(f)

    # Load second shift groups
    second_shift_groups = load_second_shift_groups(groups_second_shift_path)

    # Create room manager
    room_manager = RoomManager(
        rooms_csv,
        subject_rooms=subject_rooms,
        instructor_rooms=instructor_rooms,
        group_buildings=group_buildings,
    )

    # Create conflict tracker
    conflict_tracker = ConflictTracker(
        instructor_availability=instructor_availability,
        nearby_buildings=nearby_buildings,
        instructor_day_constraints=instructor_days,
    )

    return Stage7Scheduler(
        room_manager=room_manager,
        conflict_tracker=conflict_tracker,
        instructor_availability=instructor_availability,
        second_shift_groups=second_shift_groups,
    )
