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
    Room,
    ScheduleResult,
    ScheduleStatistics,
    UnscheduledReason,
    UnscheduledStream,
    WeekType,
)
from .rooms import RoomManager
from .utils import filter_stage1_lectures, sort_streams_by_priority


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
    ) -> None:
        """Initialize the Stage 1 scheduler.

        Args:
            rooms_csv: Path to rooms.csv file
            subject_rooms: Dictionary from subject-rooms.json
            instructor_rooms: Dictionary from instructor-rooms.json
            group_buildings: Dictionary from group-buildings.json
            instructor_availability: List from instructor-availability.json
        """
        self.instructor_availability = instructor_availability
        self.conflict_tracker = ConflictTracker(instructor_availability)
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
            )
            assignments.append(assignment)

            # Reserve resources
            self.conflict_tracker.reserve(
                stream.instructor, stream.groups, day, slot, WeekType.BOTH
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
                for i in range(hours):
                    if first_room and self.room_manager.is_room_available(
                        first_room.name, day, slot + i, WeekType.BOTH
                    ):
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
                    if first_room is None:
                        first_room = room

                if rooms_available:
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
) -> Stage1Scheduler:
    """Factory function to create a Stage1Scheduler with loaded reference data.

    Args:
        rooms_csv: Path to rooms.csv file
        subject_rooms_json: Path to subject-rooms.json file (optional)
        instructor_rooms_json: Path to instructor-rooms.json file (optional)
        group_buildings_json: Path to group-buildings.json file (optional)
        instructor_availability_json: Path to instructor-availability.json file (optional)

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

    return Stage1Scheduler(
        rooms_path,
        subject_rooms,
        instructor_rooms,
        group_buildings,
        instructor_availability,
    )
