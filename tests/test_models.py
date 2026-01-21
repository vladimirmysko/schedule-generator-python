"""Tests for data models."""

import pytest

from form1_parser.exceptions import InvalidHoursError
from form1_parser.models import (
    ParseResult,
    Stream,
    StreamType,
    SubjectSummary,
    WeeklyHours,
)


class TestWeeklyHours:
    """Tests for WeeklyHours model."""

    def test_from_total_zero(self):
        """Test calculation with zero hours."""
        hours = WeeklyHours.from_total(0)
        assert hours.total == 0
        assert hours.odd_week == 0
        assert hours.even_week == 0

    def test_from_total_7_hours(self):
        """Test 7 hours (even weeks only)."""
        hours = WeeklyHours.from_total(7)
        assert hours.total == 7
        assert hours.odd_week == 0
        assert hours.even_week == 1

    def test_from_total_8_hours(self):
        """Test 8 hours (odd weeks only)."""
        hours = WeeklyHours.from_total(8)
        assert hours.total == 8
        assert hours.odd_week == 1
        assert hours.even_week == 0

    def test_from_total_15_hours(self):
        """Test 15 hours (1 per week)."""
        hours = WeeklyHours.from_total(15)
        assert hours.total == 15
        assert hours.odd_week == 1
        assert hours.even_week == 1

    def test_from_total_22_hours(self):
        """Test 22 hours (1 odd, 2 even)."""
        hours = WeeklyHours.from_total(22)
        assert hours.total == 22
        assert hours.odd_week == 1
        assert hours.even_week == 2

    def test_from_total_23_hours(self):
        """Test 23 hours (2 odd, 1 even)."""
        hours = WeeklyHours.from_total(23)
        assert hours.total == 23
        assert hours.odd_week == 2
        assert hours.even_week == 1

    def test_from_total_30_hours(self):
        """Test 30 hours (2 per week)."""
        hours = WeeklyHours.from_total(30)
        assert hours.total == 30
        assert hours.odd_week == 2
        assert hours.even_week == 2

    def test_from_total_38_hours(self):
        """Test 38 hours (3 odd, 2 even)."""
        hours = WeeklyHours.from_total(38)
        assert hours.total == 38
        assert hours.odd_week == 3
        assert hours.even_week == 2

    def test_from_total_45_hours(self):
        """Test 45 hours (3 per week)."""
        hours = WeeklyHours.from_total(45)
        assert hours.total == 45
        assert hours.odd_week == 3
        assert hours.even_week == 3

    def test_from_total_invalid_hours(self):
        """Test invalid hours raises error."""
        with pytest.raises(InvalidHoursError):
            WeeklyHours.from_total(10)  # 10 % 15 = 10, not 0, 7, or 8

    def test_str_representation(self):
        """Test string representation."""
        hours = WeeklyHours.from_total(30)
        assert str(hours) == "30h (odd:2, even:2)"


class TestStreamType:
    """Tests for StreamType enum."""

    def test_lecture_value(self):
        assert StreamType.LECTURE.value == "lecture"

    def test_practical_value(self):
        assert StreamType.PRACTICAL.value == "practical"

    def test_lab_value(self):
        assert StreamType.LAB.value == "lab"


class TestStream:
    """Tests for Stream model."""

    def test_stream_creation(self):
        """Test creating a stream."""
        hours = WeeklyHours.from_total(15)
        stream = Stream(
            id="test_001",
            subject="Mathematics",
            stream_type=StreamType.LECTURE,
            instructor="Иванов А.О.",
            language="каз",
            hours=hours,
            groups=["СТР-21 О", "СТР-22 О"],
            student_count=50,
            sheet="оод (2)",
            rows=[10, 11],
        )

        assert stream.id == "test_001"
        assert stream.subject == "Mathematics"
        assert stream.stream_type == StreamType.LECTURE
        assert stream.instructor == "Иванов А.О."
        assert len(stream.groups) == 2
        assert stream.is_subgroup is False
        assert stream.is_implicit_subgroup is False

    def test_stream_to_dict(self):
        """Test converting stream to dictionary."""
        hours = WeeklyHours.from_total(15)
        stream = Stream(
            id="test_001",
            subject="Math",
            stream_type=StreamType.LECTURE,
            instructor="Иванов",
            language="каз",
            hours=hours,
            groups=["СТР-21 О"],
            student_count=25,
            sheet="оод (2)",
            rows=[10],
        )

        data = stream.to_dict()

        assert data["id"] == "test_001"
        assert data["stream_type"] == "lecture"
        assert data["hours"]["total"] == 15
        assert data["hours"]["odd_week"] == 1


class TestSubjectSummary:
    """Tests for SubjectSummary model."""

    def test_total_streams(self):
        """Test total_streams property."""
        hours = WeeklyHours.from_total(15)
        lecture = Stream(
            id="lec_001",
            subject="Math",
            stream_type=StreamType.LECTURE,
            instructor="Иванов",
            language="каз",
            hours=hours,
            groups=["СТР-21 О"],
            student_count=25,
            sheet="оод (2)",
            rows=[10],
        )
        practical = Stream(
            id="prac_001",
            subject="Math",
            stream_type=StreamType.PRACTICAL,
            instructor="Иванов",
            language="каз",
            hours=hours,
            groups=["СТР-21 О"],
            student_count=25,
            sheet="оод (2)",
            rows=[10],
        )

        summary = SubjectSummary(
            subject="Math",
            sheet="оод (2)",
            pattern="1a",
            lecture_streams=[lecture],
            practical_streams=[practical],
            lab_streams=[],
        )

        assert summary.total_streams == 2

    def test_instructors_property(self):
        """Test instructors property returns unique sorted list."""
        hours = WeeklyHours.from_total(15)

        stream1 = Stream(
            id="s1",
            subject="Math",
            stream_type=StreamType.LECTURE,
            instructor="Иванов",
            language="каз",
            hours=hours,
            groups=["СТР-21 О"],
            student_count=25,
            sheet="оод (2)",
            rows=[10],
        )
        stream2 = Stream(
            id="s2",
            subject="Math",
            stream_type=StreamType.PRACTICAL,
            instructor="Петров",
            language="каз",
            hours=hours,
            groups=["СТР-21 О"],
            student_count=25,
            sheet="оод (2)",
            rows=[11],
        )
        stream3 = Stream(
            id="s3",
            subject="Math",
            stream_type=StreamType.PRACTICAL,
            instructor="Иванов",  # Duplicate
            language="каз",
            hours=hours,
            groups=["СТР-22 О"],
            student_count=28,
            sheet="оод (2)",
            rows=[12],
        )

        summary = SubjectSummary(
            subject="Math",
            sheet="оод (2)",
            pattern="1a",
            lecture_streams=[stream1],
            practical_streams=[stream2, stream3],
            lab_streams=[],
        )

        assert summary.instructors == ["Иванов", "Петров"]


class TestParseResult:
    """Tests for ParseResult model."""

    def test_empty_result(self):
        """Test empty parse result."""
        result = ParseResult(
            file_path="test.xlsx",
            parse_date="2025-01-01",
        )

        assert result.total_subjects == 0
        assert result.total_streams == 0
        assert result.errors == []
        assert result.warnings == []

    def test_to_dict(self):
        """Test converting result to dictionary."""
        result = ParseResult(
            file_path="test.xlsx",
            parse_date="2025-01-01",
            sheets_processed=["оод (2)"],
            errors=["Some error"],
        )

        data = result.to_dict()

        assert data["file_path"] == "test.xlsx"
        assert data["total_subjects"] == 0
        assert data["total_streams"] == 0
        assert len(data["errors"]) == 1
