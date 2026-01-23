"""Solution extraction from CP-SAT solver."""

from typing import TYPE_CHECKING

from ortools.sat.python import cp_model

from ..constants import FIRST_SHIFT_SLOTS
from ..models import (
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

if TYPE_CHECKING:
    from ..config import ConfigLoader


class SolutionExtractor:
    """Extracts solution from solved CP-SAT model."""

    def __init__(
        self,
        solver: cp_model.CpSolver,
        variables: dict,
        streams: list[LectureStream],
        rooms: list[Room],
        config: "ConfigLoader",
        week_type: WeekType = WeekType.BOTH,
    ):
        self.solver = solver
        self.variables = variables
        self.streams = streams
        self.rooms = rooms
        self.config = config
        self.week_type = week_type

        self._stream_by_id = {s.id: s for s in streams}
        self._room_by_key = {(r.name, r.address): r for r in rooms}

    def extract(self) -> ScheduleResult:
        """
        Extract the schedule result from solver.

        Returns ScheduleResult with assignments and unscheduled streams.
        """
        assignments = self._extract_assignments()
        unscheduled = self._extract_unscheduled()
        statistics = self._compute_statistics(assignments, unscheduled)

        return ScheduleResult(
            assignments=assignments,
            unscheduled_streams=unscheduled,
            statistics=statistics,
            week_type=self.week_type,
            stage=1,
        )

    def _extract_assignments(self) -> list[Assignment]:
        """Extract scheduled assignments from solver."""
        assignments = []
        x = self.variables["x"]

        for key, var in x.items():
            if self.solver.Value(var) == 1:
                stream_id, hour_idx, day, slot, room_name, room_address = key
                stream = self._stream_by_id.get(stream_id)

                if stream is None:
                    continue

                assignment = Assignment(
                    stream_id=stream.id,
                    subject=stream.subject,
                    stream_type=stream.stream_type,
                    instructor=stream.instructor,
                    language=stream.language,
                    groups=stream.groups,
                    student_count=stream.student_count,
                    day=day,
                    slot=slot,
                    room=room_name,
                    room_address=room_address,
                    week_type=self.week_type,
                )
                assignments.append(assignment)

        return assignments

    def _extract_unscheduled(self) -> list[UnscheduledStream]:
        """Extract unscheduled streams with failure reasons."""
        unscheduled = []
        x = self.variables["x"]
        scheduled_vars = self.variables.get("scheduled", {})

        # Find streams that have at least one assignment (check hour_idx 0)
        scheduled_ids = set()
        for key, var in x.items():
            if self.solver.Value(var) == 1 and key[1] == 0:  # hour_idx == 0
                scheduled_ids.add(key[0])

        for stream in self.streams:
            if stream.id in scheduled_ids:
                continue

            # Analyze why stream wasn't scheduled
            reason, details = self._analyze_failure(stream)

            unscheduled.append(UnscheduledStream(
                stream_id=stream.id,
                subject=stream.subject,
                stream_type=stream.stream_type,
                instructor=stream.instructor,
                groups=stream.groups,
                student_count=stream.student_count,
                reason=reason,
                details=details,
            ))

        return unscheduled

    def _analyze_failure(self, stream: LectureStream) -> tuple[UnscheduledReason, str]:
        """Analyze why a stream couldn't be scheduled."""
        x = self.variables["x"]

        # Check if stream has any variables at all (check first hour)
        stream_vars = [
            (key, var) for key, var in x.items()
            if key[0] == stream.id and key[1] == 0
        ]

        if not stream_vars:
            # No valid room/slot combinations
            # Check what's missing
            available_rooms = self._count_available_rooms(stream)
            if available_rooms == 0:
                return (
                    UnscheduledReason.NO_ROOM_AVAILABLE,
                    f"No room available with capacity >= {stream.student_count} students"
                )

            return (
                UnscheduledReason.NO_SLOT_AVAILABLE,
                "No valid time slot available due to instructor/group constraints"
            )

        # Has variables but none were selected - likely due to conflicts
        return (
            UnscheduledReason.CONSTRAINT_VIOLATION,
            "Could not find assignment satisfying all constraints"
        )

    def _count_available_rooms(self, stream: LectureStream) -> int:
        """Count rooms that could potentially fit this stream."""
        count = 0
        for room in self.rooms:
            if room.is_special:
                continue
            if room.capacity >= stream.student_count:
                count += 1
        return count

    def _compute_statistics(
        self,
        assignments: list[Assignment],
        unscheduled: list[UnscheduledStream],
    ) -> ScheduleStatistics:
        """Compute schedule statistics."""
        stats = ScheduleStatistics()
        stats.total_streams = len(self.streams)
        stats.total_assigned = len(assignments)
        stats.total_unscheduled = len(unscheduled)

        # By day
        by_day: dict[str, int] = {}
        for a in assignments:
            day_name = a.day.name.lower()
            by_day[day_name] = by_day.get(day_name, 0) + 1
        stats.by_day = by_day

        # By shift
        first_shift_count = sum(
            1 for a in assignments if a.slot in FIRST_SHIFT_SLOTS
        )
        second_shift_count = len(assignments) - first_shift_count
        stats.by_shift = {
            "first": first_shift_count,
            "second": second_shift_count,
        }

        # By room
        by_room: dict[str, int] = {}
        for a in assignments:
            room_key = f"{a.room} ({a.room_address})"
            by_room[room_key] = by_room.get(room_key, 0) + 1
        stats.by_room = by_room

        # Solver time
        stats.solver_time_seconds = self.solver.WallTime()

        return stats


class FailureAnalyzer:
    """Analyzes scheduling failures in detail."""

    def __init__(
        self,
        config: "ConfigLoader",
        streams: list[LectureStream],
        rooms: list[Room],
    ):
        self.config = config
        self.streams = streams
        self.rooms = rooms

    def analyze_infeasibility(self) -> list[str]:
        """
        Analyze potential causes of infeasibility.

        Returns list of potential issues.
        """
        issues = []

        # Check for streams with no valid rooms
        for stream in self.streams:
            valid_rooms = self._get_valid_rooms(stream)
            if not valid_rooms:
                issues.append(
                    f"Stream '{stream.subject}' ({stream.instructor}): "
                    f"No room with capacity >= {stream.student_count}"
                )

        # Check for instructor unavailability covering all slots
        # This is a simplified check
        for stream in self.streams:
            all_unavailable = True
            for day in [Day.MONDAY, Day.TUESDAY, Day.WEDNESDAY, Day.THURSDAY, Day.FRIDAY]:
                unavailable = self.config.instructors.get_unavailable_slots(
                    stream.instructor, day
                )
                if len(unavailable) < 13:  # Not all slots unavailable
                    all_unavailable = False
                    break
            if all_unavailable:
                issues.append(
                    f"Instructor '{stream.instructor}': "
                    "Unavailable during all time slots"
                )

        return issues

    def _get_valid_rooms(self, stream: LectureStream) -> list[Room]:
        """Get rooms that could fit this stream."""
        valid = []
        for room in self.rooms:
            if room.is_special:
                continue
            if room.capacity >= stream.student_count:
                valid.append(room)
        return valid
