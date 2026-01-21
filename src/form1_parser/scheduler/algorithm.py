"""Stage 1 scheduling algorithm for multi-group lectures."""

from collections import defaultdict
from datetime import datetime
from pathlib import Path

from .conflicts import ConflictTracker
from .constants import get_slots_for_shift
from .models import (
    Assignment,
    Day,
    LectureStream,
    Room,
    ScheduleResult,
    ScheduleStatistics,
    WeekType,
)
from .rooms import RoomManager
from .utils import filter_stage1_lectures, sort_streams_by_priority


class Stage1Scheduler:
    """Scheduler for Stage 1: multi-group lectures on Mon/Tue/Wed.

    Stage 1 Requirements:
    1. Filter: Only lectures with 2+ groups
    2. Sort: By largest number of students (descending)
    3. Days: Monday, Tuesday, Wednesday only
    4. Multi-hour: If odd_week > 1 or even_week > 1, assign 2 back-to-back classes
    5. Even distribution: Each group's lectures evenly distributed among 3 days
    6. Shift start: Lectures begin at the beginning of the shift
    7. Same position: Odd and even weeks use the same (day, slot) for consistency
    8. Room assignment: Assign rooms based on capacity and constraints
    """

    # Stage 1 only schedules on these days
    STAGE1_DAYS = [Day.MONDAY, Day.TUESDAY, Day.WEDNESDAY]

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
        lectures = filter_stage1_lectures(streams)

        # 2. Sort by student_count descending (largest first = highest priority)
        prepared = sort_streams_by_priority(lectures)

        # 3. Schedule each stream
        assignments: list[Assignment] = []
        unscheduled: list[str] = []

        for stream in prepared:
            result = self._schedule_stream(stream)
            if result:
                assignments.extend(result)
            else:
                unscheduled.append(stream.id)

        # 4. Compute statistics
        statistics = self._compute_statistics(assignments)

        return ScheduleResult(
            generation_date=datetime.now().isoformat(),
            stage=1,
            assignments=assignments,
            unscheduled_stream_ids=unscheduled,
            statistics=statistics,
        )

    def _schedule_stream(self, stream: LectureStream) -> list[Assignment] | None:
        """Schedule a single stream at the same position for both odd and even weeks.

        Args:
            stream: LectureStream to schedule

        Returns:
            List of Assignment objects or None if unable to schedule
        """
        # Determine max hours needed (use the larger of odd/even)
        hours = stream.max_hours
        if hours == 0:
            return []

        # Find best position (day, starting_slot)
        position = self._find_best_position(stream, hours)
        if not position:
            return None

        day, start_slot = position
        assignments = []

        # Find rooms for all consecutive slots first
        rooms: list[Room] = []
        for i in range(hours):
            slot = start_slot + i
            room = self.room_manager.find_room(stream, day, slot)
            if not room:
                return None  # No room available for this slot
            rooms.append(room)

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
    ) -> tuple[Day, int] | None:
        """Find the best (day, starting_slot) for a stream.

        Strategy:
        1. Get valid slots for the stream's shift
        2. Sort days by load (prefer least loaded for these groups)
        3. Try earliest slots first (start at beginning of shift)
        4. Check consecutive slots if hours > 1

        Args:
            stream: LectureStream to schedule
            hours: Number of consecutive hours needed

        Returns:
            Tuple of (Day, start_slot) or None if no position found
        """
        # Get valid slots for this stream's shift
        valid_slots = get_slots_for_shift(stream.shift)

        # Sort days by total load for these groups (prefer least loaded)
        day_loads = {
            day: self.conflict_tracker.get_groups_total_daily_load(stream.groups, day)
            for day in self.STAGE1_DAYS
        }
        sorted_days = sorted(day_loads.keys(), key=lambda d: day_loads[d])

        for day in sorted_days:
            # Try slots in order (ascending - prefer earliest)
            for slot in valid_slots:
                # Check if we have enough consecutive slots
                if hours > 1:
                    # Verify all consecutive slots are in valid_slots
                    consecutive_valid = all(
                        (slot + i) in valid_slots for i in range(hours)
                    )
                    if not consecutive_valid:
                        continue

                # Check availability for all consecutive slots
                if not self.conflict_tracker.are_consecutive_slots_available(
                    stream.instructor,
                    stream.groups,
                    day,
                    slot,
                    hours,
                    WeekType.BOTH,
                ):
                    continue

                # Verify rooms are available for all slots
                rooms_available = True
                for i in range(hours):
                    room = self.room_manager.find_room(stream, day, slot + i)
                    if not room:
                        rooms_available = False
                        break

                if rooms_available:
                    return (day, slot)

        return None

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
