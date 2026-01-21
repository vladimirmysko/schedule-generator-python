"""Data models for schedule generation."""

from dataclasses import dataclass, field
from enum import Enum

from .constants import Shift, get_slot_time_range


class Day(str, Enum):
    """Day of the week."""

    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"


class WeekType(str, Enum):
    """Week type for scheduling."""

    ODD = "odd"
    EVEN = "even"
    BOTH = "both"


class UnscheduledReason(str, Enum):
    """Reason why a stream could not be scheduled."""

    INSTRUCTOR_CONFLICT = "instructor_conflict"
    GROUP_CONFLICT = "group_conflict"
    NO_ROOM_AVAILABLE = "no_room_available"
    INSTRUCTOR_UNAVAILABLE = "instructor_unavailable"
    NO_CONSECUTIVE_SLOTS = "no_consecutive_slots"
    ALL_SLOTS_EXHAUSTED = "all_slots_exhausted"
    BUILDING_GAP_REQUIRED = "building_gap_required"
    # Stage 2 specific reasons
    NO_LECTURE_DEPENDENCY = "no_lecture_dependency"
    SUBJECT_DAILY_LIMIT_EXCEEDED = "subject_daily_limit_exceeded"
    DAILY_LOAD_EXCEEDED = "daily_load_exceeded"
    MAX_WINDOWS_EXCEEDED = "max_windows_exceeded"
    INSTRUCTOR_DAY_CONSTRAINT = "instructor_day_constraint"


@dataclass
class TimeSlot:
    """A time slot for scheduling."""

    slot_number: int
    start_time: str
    end_time: str
    shift: Shift

    def __str__(self) -> str:
        return f"Slot {self.slot_number}: {self.start_time}-{self.end_time} ({self.shift.value})"


@dataclass
class GroupInfo:
    """Parsed group information."""

    name: str
    year: int  # 1-5
    shift: Shift
    specialty_code: str  # e.g., "АРХ", "СТР", "НД"
    student_count: int = 0


@dataclass
class LectureStream:
    """Prepared stream for scheduling with priority info."""

    id: str
    subject: str
    instructor: str
    language: str
    groups: list[str]
    student_count: int
    hours_odd_week: int
    hours_even_week: int
    shift: Shift
    sheet: str
    instructor_available_slots: int = 0  # Available slots for this instructor
    subject_prac_lab_hours: int = 0  # Total practical + lab hours for subject

    @property
    def max_hours(self) -> int:
        """Maximum hours needed per week."""
        return max(self.hours_odd_week, self.hours_even_week)


@dataclass
class LectureDependency:
    """Information about a lecture that a practical depends on."""

    lecture_id: str
    day: Day
    end_slot: int  # Last slot of the lecture
    groups: list[str]  # Groups that attend this lecture


@dataclass
class PracticalStream:
    """Prepared practical stream for Stage 2 scheduling."""

    id: str
    subject: str
    instructor: str
    language: str
    groups: list[str]
    student_count: int
    hours_odd_week: int
    hours_even_week: int
    shift: Shift
    sheet: str
    stream_type: str  # "practical" or "lab"
    lecture_dependency: LectureDependency | None = None
    complexity_score: float = 0.0

    @property
    def max_hours(self) -> int:
        """Maximum hours needed per week."""
        return max(self.hours_odd_week, self.hours_even_week)


@dataclass
class Room:
    """A room for scheduling."""

    name: str
    capacity: int
    address: str
    is_special: bool = False

    def __str__(self) -> str:
        return f"{self.name} ({self.capacity}) @ {self.address}"


@dataclass
class Assignment:
    """A scheduled assignment."""

    stream_id: str
    subject: str
    instructor: str
    groups: list[str]
    student_count: int
    day: Day
    slot: int
    room: str
    room_address: str
    week_type: WeekType = WeekType.BOTH

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "stream_id": self.stream_id,
            "subject": self.subject,
            "instructor": self.instructor,
            "groups": self.groups,
            "student_count": self.student_count,
            "day": self.day.value,
            "slot": self.slot,
            "time": get_slot_time_range(self.slot),
            "room": self.room,
            "room_address": self.room_address,
            "week_type": self.week_type.value,
        }


@dataclass
class UnscheduledStream:
    """Information about a stream that could not be scheduled."""

    stream_id: str
    subject: str
    instructor: str
    groups: list[str]
    student_count: int
    shift: Shift
    reason: UnscheduledReason
    details: str = ""  # Additional context about why scheduling failed

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "stream_id": self.stream_id,
            "subject": self.subject,
            "instructor": self.instructor,
            "groups": self.groups,
            "student_count": self.student_count,
            "shift": self.shift.value,
            "reason": self.reason.value,
            "details": self.details,
        }


@dataclass
class ScheduleStatistics:
    """Statistics for the generated schedule."""

    by_day: dict[str, int] = field(default_factory=dict)
    by_shift: dict[str, int] = field(default_factory=dict)
    room_utilization: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "by_day": self.by_day,
            "by_shift": self.by_shift,
            "room_utilization": self.room_utilization,
        }


@dataclass
class ScheduleResult:
    """Result of schedule generation."""

    generation_date: str
    stage: int
    assignments: list[Assignment] = field(default_factory=list)
    unscheduled_stream_ids: list[str] = field(default_factory=list)
    unscheduled_streams: list[UnscheduledStream] = field(default_factory=list)
    statistics: ScheduleStatistics = field(default_factory=ScheduleStatistics)

    @property
    def total_assigned(self) -> int:
        """Total number of assignments."""
        return len(self.assignments)

    @property
    def total_unscheduled(self) -> int:
        """Total number of unscheduled streams."""
        return len(self.unscheduled_stream_ids)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "generation_date": self.generation_date,
            "stage": self.stage,
            "total_assigned": self.total_assigned,
            "total_unscheduled": self.total_unscheduled,
            "assignments": [a.to_dict() for a in self.assignments],
            "unscheduled_stream_ids": self.unscheduled_stream_ids,
            "unscheduled_streams": [s.to_dict() for s in self.unscheduled_streams],
            "statistics": self.statistics.to_dict(),
        }
