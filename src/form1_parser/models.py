"""Data models for Form-1 parser."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Self

from .exceptions import InvalidHoursError


class StreamType(Enum):
    """Type of academic stream."""

    LECTURE = "lecture"
    PRACTICAL = "practical"
    LAB = "lab"


@dataclass
class WeeklyHours:
    """Hours per week for scheduling.

    Attributes:
        total: Total semester hours (from spreadsheet)
        odd_week: Hours on odd weeks (1,3,5,7,9,11,13,15)
        even_week: Hours on even weeks (2,4,6,8,10,12,14)
    """

    total: int
    odd_week: int
    even_week: int

    @classmethod
    def from_total(cls, total_hours: int) -> Self:
        """Calculate weekly hours from total semester hours.

        Formula: total = odd_week × 8 + even_week × 7

        Args:
            total_hours: Total semester hours from spreadsheet

        Returns:
            WeeklyHours instance

        Raises:
            InvalidHoursError: If total_hours doesn't fit the formula
        """
        if total_hours == 0:
            return cls(total=0, odd_week=0, even_week=0)

        remainder = total_hours % 15
        base = total_hours // 15

        if remainder == 0:
            return cls(total=total_hours, odd_week=base, even_week=base)
        elif remainder == 8:
            return cls(total=total_hours, odd_week=base + 1, even_week=base)
        elif remainder == 7:
            return cls(total=total_hours, odd_week=base, even_week=base + 1)
        else:
            raise InvalidHoursError(total_hours)

    def __str__(self) -> str:
        return f"{self.total}h (odd:{self.odd_week}, even:{self.even_week})"


@dataclass
class Stream:
    """A single academic stream.

    A stream is uniquely identified by subject, class type, and instructor.
    If different instructor → different stream.

    Attributes:
        id: Unique identifier
        subject: Subject name
        stream_type: lecture/practical/lab
        instructor: Instructor name (from last column)
        language: каз or орыс
        hours: Hours breakdown (total + per week)
        groups: List of group names in this stream
        student_count: Total students in stream
        sheet: Source sheet name
        rows: Source row numbers
        is_subgroup: True if explicit subgroup notation
        is_implicit_subgroup: True if implicit subgroup (repeated group)
    """

    id: str
    subject: str
    stream_type: StreamType
    instructor: str
    language: str
    hours: WeeklyHours
    groups: list[str]
    student_count: int
    sheet: str
    rows: list[int]
    is_subgroup: bool = False
    is_implicit_subgroup: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "subject": self.subject,
            "stream_type": self.stream_type.value,
            "instructor": self.instructor,
            "language": self.language,
            "hours": {
                "total": self.hours.total,
                "odd_week": self.hours.odd_week,
                "even_week": self.hours.even_week,
            },
            "groups": self.groups,
            "student_count": self.student_count,
            "sheet": self.sheet,
            "rows": self.rows,
            "is_subgroup": self.is_subgroup,
            "is_implicit_subgroup": self.is_implicit_subgroup,
        }


@dataclass
class SubjectSummary:
    """Summary of streams for a single subject.

    Attributes:
        subject: Subject name
        sheet: Source sheet name
        pattern: Detected pattern ("1a", "1b", "implicit_subgroup", "explicit_subgroup")
        lecture_streams: List of lecture streams
        practical_streams: List of practical streams
        lab_streams: List of lab streams
    """

    subject: str
    sheet: str
    pattern: str
    lecture_streams: list[Stream] = field(default_factory=list)
    practical_streams: list[Stream] = field(default_factory=list)
    lab_streams: list[Stream] = field(default_factory=list)

    @property
    def total_streams(self) -> int:
        """Total number of streams for this subject."""
        return len(self.lecture_streams) + len(self.practical_streams) + len(self.lab_streams)

    @property
    def total_hours(self) -> int:
        """Total hours across all streams."""
        total = 0
        for stream in self.lecture_streams + self.practical_streams + self.lab_streams:
            total += stream.hours.total
        return total

    @property
    def instructors(self) -> list[str]:
        """List of unique instructors for this subject."""
        instructors = set()
        for stream in self.lecture_streams + self.practical_streams + self.lab_streams:
            instructors.add(stream.instructor)
        return sorted(instructors)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "subject": self.subject,
            "sheet": self.sheet,
            "pattern": self.pattern,
            "total_streams": self.total_streams,
            "total_hours": self.total_hours,
            "instructors": self.instructors,
            "lecture_streams": [s.to_dict() for s in self.lecture_streams],
            "practical_streams": [s.to_dict() for s in self.practical_streams],
            "lab_streams": [s.to_dict() for s in self.lab_streams],
        }


@dataclass
class ParseResult:
    """Result of parsing a Form-1 file.

    Attributes:
        file_path: Path to the parsed file
        parse_date: Date of parsing (ISO format)
        sheets_processed: List of successfully processed sheet names
        subjects: List of subject summaries
        streams: List of all streams
        errors: List of error messages
        warnings: List of warning messages
    """

    file_path: str
    parse_date: str
    sheets_processed: list[str] = field(default_factory=list)
    subjects: list[SubjectSummary] = field(default_factory=list)
    streams: list[Stream] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def total_subjects(self) -> int:
        """Total number of unique subjects."""
        return len(self.subjects)

    @property
    def total_streams(self) -> int:
        """Total number of streams."""
        return len(self.streams)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "file_path": self.file_path,
            "parse_date": self.parse_date,
            "sheets_processed": self.sheets_processed,
            "total_subjects": self.total_subjects,
            "total_streams": self.total_streams,
            "subjects": [s.to_dict() for s in self.subjects],
            "streams": [s.to_dict() for s in self.streams],
            "errors": self.errors,
            "warnings": self.warnings,
        }
