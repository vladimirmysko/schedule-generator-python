"""Data models for the university course scheduling system."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Day(Enum):
    """Days of the academic week."""

    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5  # Not used in scheduling but included for completeness


class WeekType(str, Enum):
    """Week type for scheduling (odd, even, or both)."""

    ODD = "odd"
    EVEN = "even"
    BOTH = "both"


class StreamType(str, Enum):
    """Type of academic stream."""

    LECTURE = "lecture"
    PRACTICAL = "practical"
    LAB = "lab"


class UnscheduledReason(str, Enum):
    """Reasons why a stream could not be scheduled."""

    NO_ROOM_AVAILABLE = "no_room_available"
    NO_SLOT_AVAILABLE = "no_slot_available"
    INSTRUCTOR_UNAVAILABLE = "instructor_unavailable"
    SHIFT_CONFLICT = "shift_conflict"
    BUILDING_CONFLICT = "building_conflict"
    CAPACITY_EXCEEDED = "capacity_exceeded"
    CONSTRAINT_VIOLATION = "constraint_violation"
    SOLVER_TIMEOUT = "solver_timeout"
    INFEASIBLE = "infeasible"
    UNKNOWN = "unknown"


@dataclass
class Room:
    """A physical room for scheduling."""

    name: str
    capacity: int
    address: str
    is_special: bool = False

    def __hash__(self) -> int:
        return hash((self.name, self.address))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Room):
            return False
        return self.name == other.name and self.address == other.address


@dataclass
class LectureStream:
    """A stream prepared for scheduling."""

    id: str
    subject: str
    stream_type: StreamType
    instructor: str
    language: str
    groups: list[str]
    student_count: int
    hours_odd: int
    hours_even: int
    sheet: str
    is_subgroup: bool = False
    is_implicit_subgroup: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LectureStream":
        """Create a LectureStream from a dictionary."""
        hours = data.get("hours", {})
        return cls(
            id=data["id"],
            subject=data["subject"],
            stream_type=StreamType(data["stream_type"]),
            instructor=data["instructor"],
            language=data.get("language", ""),
            groups=data.get("groups", []),
            student_count=data.get("student_count", 0),
            hours_odd=hours.get("odd_week", 0),
            hours_even=hours.get("even_week", 0),
            sheet=data.get("sheet", ""),
            is_subgroup=data.get("is_subgroup", False),
            is_implicit_subgroup=data.get("is_implicit_subgroup", False),
        )

    def get_hours(self, week_type: WeekType) -> int:
        """Get the number of hours for a given week type."""
        if week_type == WeekType.ODD:
            return self.hours_odd
        elif week_type == WeekType.EVEN:
            return self.hours_even
        else:  # BOTH - return the max for scheduling purposes
            return max(self.hours_odd, self.hours_even)


@dataclass
class Assignment:
    """A scheduled class assignment."""

    stream_id: str
    subject: str
    stream_type: StreamType
    instructor: str
    language: str
    groups: list[str]
    student_count: int
    day: Day
    slot: int
    room: str
    room_address: str
    week_type: WeekType

    def to_dict(self) -> dict[str, Any]:
        """Convert assignment to dictionary."""
        return {
            "stream_id": self.stream_id,
            "subject": self.subject,
            "stream_type": self.stream_type.value,
            "instructor": self.instructor,
            "language": self.language,
            "groups": self.groups,
            "student_count": self.student_count,
            "day": self.day.name.lower(),
            "slot": self.slot,
            "room": self.room,
            "room_address": self.room_address,
            "week_type": self.week_type.value,
        }


@dataclass
class UnscheduledStream:
    """A stream that could not be scheduled."""

    stream_id: str
    subject: str
    stream_type: StreamType
    instructor: str
    groups: list[str]
    student_count: int
    reason: UnscheduledReason
    details: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "stream_id": self.stream_id,
            "subject": self.subject,
            "stream_type": self.stream_type.value,
            "instructor": self.instructor,
            "groups": self.groups,
            "student_count": self.student_count,
            "reason": self.reason.value,
            "details": self.details,
        }


@dataclass
class ScheduleStatistics:
    """Statistics about the generated schedule."""

    total_streams: int = 0
    total_assigned: int = 0
    total_unscheduled: int = 0
    by_day: dict[str, int] = field(default_factory=dict)
    by_shift: dict[str, int] = field(default_factory=dict)
    by_room: dict[str, int] = field(default_factory=dict)
    constraint_penalties: dict[str, float] = field(default_factory=dict)
    solver_time_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_streams": self.total_streams,
            "total_assigned": self.total_assigned,
            "total_unscheduled": self.total_unscheduled,
            "scheduling_rate": (
                self.total_assigned / self.total_streams
                if self.total_streams > 0
                else 0.0
            ),
            "by_day": self.by_day,
            "by_shift": self.by_shift,
            "by_room": self.by_room,
            "constraint_penalties": self.constraint_penalties,
            "solver_time_seconds": self.solver_time_seconds,
        }


@dataclass
class ScheduleResult:
    """Result of the scheduling process."""

    assignments: list[Assignment] = field(default_factory=list)
    unscheduled_streams: list[UnscheduledStream] = field(default_factory=list)
    statistics: ScheduleStatistics = field(default_factory=ScheduleStatistics)
    generation_date: str = field(default_factory=lambda: datetime.now().isoformat())
    week_type: WeekType = WeekType.BOTH
    stage: int = 1

    @property
    def total_assigned(self) -> int:
        """Total number of assigned slots."""
        return len(self.assignments)

    @property
    def total_unscheduled(self) -> int:
        """Total number of unscheduled streams."""
        return len(self.unscheduled_streams)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "generation_date": self.generation_date,
            "week_type": self.week_type.value,
            "stage": self.stage,
            "assignments": [a.to_dict() for a in self.assignments],
            "unscheduled_streams": [u.to_dict() for u in self.unscheduled_streams],
            "unscheduled_stream_ids": [u.stream_id for u in self.unscheduled_streams],
            "statistics": self.statistics.to_dict(),
        }
