"""Tests for Stage1Scheduler class."""

import csv
import tempfile
from pathlib import Path

import pytest

from form1_parser.scheduler.algorithm import Stage1Scheduler, create_scheduler
from form1_parser.scheduler.constants import FLEXIBLE_SCHEDULE_SUBJECTS
from form1_parser.scheduler.models import Day, UnscheduledReason
from form1_parser.scheduler.utils import filter_stage1_lectures, sort_streams_by_priority


@pytest.fixture
def temp_rooms_csv():
    """Create a temporary rooms.csv file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        writer = csv.DictWriter(f, fieldnames=["name", "capacity", "address", "is_special"])
        writer.writeheader()
        writer.writerows(
            [
                {"name": "Room-50", "capacity": "50", "address": "Address 1", "is_special": ""},
                {"name": "Room-100", "capacity": "100", "address": "Address 1", "is_special": ""},
                {"name": "Room-150", "capacity": "150", "address": "Address 1", "is_special": ""},
                {"name": "Room-200", "capacity": "200", "address": "Address 1", "is_special": ""},
            ]
        )
        return Path(f.name)


@pytest.fixture
def sample_streams():
    """Create sample stream data for testing."""
    return [
        {
            "id": "stream1",
            "stream_type": "lecture",
            "subject": "Subject 1",
            "instructor": "Instructor 1",
            "language": "каз",
            "groups": ["Group-11", "Group-13"],  # Year 1 groups -> First shift
            "student_count": 100,
            "hours": {"odd_week": 1, "even_week": 1},
            "sheet": "sheet1",
        },
        {
            "id": "stream2",
            "stream_type": "lecture",
            "subject": "Subject 2",
            "instructor": "Instructor 2",
            "language": "каз",
            "groups": ["Group-11", "Group-15"],  # Year 1 groups -> First shift
            "student_count": 75,
            "hours": {"odd_week": 1, "even_week": 1},
            "sheet": "sheet1",
        },
        {
            "id": "stream3",
            "stream_type": "practical",  # Should be filtered out
            "subject": "Subject 3",
            "instructor": "Instructor 3",
            "language": "каз",
            "groups": ["Group-21", "Group-23"],
            "student_count": 50,
            "hours": {"odd_week": 1, "even_week": 1},
            "sheet": "sheet1",
        },
        {
            "id": "stream4",
            "stream_type": "lecture",
            "subject": "Subject 4",
            "instructor": "Instructor 4",
            "language": "каз",
            "groups": ["Group-21"],  # Only 1 group - should be filtered out
            "student_count": 25,
            "hours": {"odd_week": 1, "even_week": 1},
            "sheet": "sheet1",
        },
    ]


class TestStage1Scheduler:
    """Tests for Stage1Scheduler class."""

    def test_schedules_lectures_with_2_plus_groups(self, temp_rooms_csv, sample_streams):
        scheduler = Stage1Scheduler(temp_rooms_csv)
        result = scheduler.schedule(sample_streams)

        # Should schedule stream1 and stream2 only
        # stream3 is practical, stream4 has only 1 group
        assert result.total_assigned >= 2  # At least 2 assignments (one per stream)
        assert result.total_unscheduled == 0

    def test_assigns_to_valid_days(self, temp_rooms_csv, sample_streams):
        scheduler = Stage1Scheduler(temp_rooms_csv)
        result = scheduler.schedule(sample_streams)

        valid_days = {Day.MONDAY, Day.TUESDAY, Day.WEDNESDAY}
        for assignment in result.assignments:
            assert assignment.day in valid_days

    def test_no_instructor_conflicts(self, temp_rooms_csv):
        # Create streams with same instructor
        streams = [
            {
                "id": "stream1",
                "stream_type": "lecture",
                "subject": "Subject 1",
                "instructor": "Same Instructor",
                "language": "каз",
                "groups": ["Group-21", "Group-23"],
                "student_count": 50,
                "hours": {"odd_week": 1, "even_week": 1},
                "sheet": "sheet1",
            },
            {
                "id": "stream2",
                "stream_type": "lecture",
                "subject": "Subject 2",
                "instructor": "Same Instructor",
                "language": "каз",
                "groups": ["Group-25", "Group-27"],
                "student_count": 50,
                "hours": {"odd_week": 1, "even_week": 1},
                "sheet": "sheet1",
            },
        ]
        scheduler = Stage1Scheduler(temp_rooms_csv)
        result = scheduler.schedule(streams)

        # Check that same instructor is not scheduled at same day/slot
        instructor_slots = {}
        for assignment in result.assignments:
            if assignment.instructor == "Same Instructor":
                key = (assignment.day, assignment.slot)
                assert key not in instructor_slots, f"Instructor conflict at {key}"
                instructor_slots[key] = assignment.stream_id

    def test_no_group_conflicts(self, temp_rooms_csv):
        # Create streams with overlapping groups
        streams = [
            {
                "id": "stream1",
                "stream_type": "lecture",
                "subject": "Subject 1",
                "instructor": "Instructor 1",
                "language": "каз",
                "groups": ["Group-21", "Group-23"],
                "student_count": 50,
                "hours": {"odd_week": 1, "even_week": 1},
                "sheet": "sheet1",
            },
            {
                "id": "stream2",
                "stream_type": "lecture",
                "subject": "Subject 2",
                "instructor": "Instructor 2",
                "language": "каз",
                "groups": ["Group-21", "Group-25"],  # Group-21 overlaps
                "student_count": 50,
                "hours": {"odd_week": 1, "even_week": 1},
                "sheet": "sheet1",
            },
        ]
        scheduler = Stage1Scheduler(temp_rooms_csv)
        result = scheduler.schedule(streams)

        # Check that Group-21 is not scheduled at same day/slot in both streams
        group_slots = {}
        for assignment in result.assignments:
            if "Group-21" in assignment.groups:
                key = (assignment.day, assignment.slot)
                if key in group_slots:
                    # Same group at same time should be same stream
                    assert (
                        group_slots[key] == assignment.stream_id
                    ), f"Group conflict at {key}"
                else:
                    group_slots[key] = assignment.stream_id

    def test_multi_hour_streams(self, temp_rooms_csv):
        streams = [
            {
                "id": "stream1",
                "stream_type": "lecture",
                "subject": "Subject 1",
                "instructor": "Instructor 1",
                "language": "каз",
                "groups": ["Group-21", "Group-23"],
                "student_count": 50,
                "hours": {"odd_week": 2, "even_week": 2},  # 2 hours
                "sheet": "sheet1",
            },
        ]
        scheduler = Stage1Scheduler(temp_rooms_csv)
        result = scheduler.schedule(streams)

        # Should have 2 assignments for this stream
        stream1_assignments = [a for a in result.assignments if a.stream_id == "stream1"]
        assert len(stream1_assignments) == 2

        # Assignments should be consecutive
        if len(stream1_assignments) == 2:
            assert stream1_assignments[0].day == stream1_assignments[1].day
            assert abs(stream1_assignments[0].slot - stream1_assignments[1].slot) == 1

    def test_assigns_rooms(self, temp_rooms_csv, sample_streams):
        scheduler = Stage1Scheduler(temp_rooms_csv)
        result = scheduler.schedule(sample_streams)

        for assignment in result.assignments:
            assert assignment.room is not None
            assert assignment.room_address is not None

    def test_statistics_computed(self, temp_rooms_csv, sample_streams):
        scheduler = Stage1Scheduler(temp_rooms_csv)
        result = scheduler.schedule(sample_streams)

        assert result.statistics is not None
        assert result.statistics.by_day is not None
        assert result.statistics.by_shift is not None

    def test_to_dict_serialization(self, temp_rooms_csv, sample_streams):
        scheduler = Stage1Scheduler(temp_rooms_csv)
        result = scheduler.schedule(sample_streams)

        data = result.to_dict()
        assert "generation_date" in data
        assert "stage" in data
        assert data["stage"] == 1
        assert "assignments" in data
        assert "unscheduled_stream_ids" in data
        assert "statistics" in data


class TestCreateScheduler:
    """Tests for create_scheduler factory function."""

    def test_creates_scheduler(self, temp_rooms_csv):
        scheduler = create_scheduler(temp_rooms_csv)
        assert isinstance(scheduler, Stage1Scheduler)

    def test_creates_scheduler_with_json_files(self, temp_rooms_csv, tmp_path):
        # Create temporary JSON files
        subject_rooms_path = tmp_path / "subject-rooms.json"
        subject_rooms_path.write_text('{"Test": {"lecture": []}}')

        instructor_rooms_path = tmp_path / "instructor-rooms.json"
        instructor_rooms_path.write_text('{"Instructor": {"lecture": []}}')

        scheduler = create_scheduler(
            temp_rooms_csv,
            subject_rooms_path,
            instructor_rooms_path,
        )
        assert isinstance(scheduler, Stage1Scheduler)


class TestUnscheduledStreams:
    """Tests for unscheduled stream tracking with failure reasons."""

    def test_unscheduled_streams_includes_detailed_info(self, temp_rooms_csv):
        """Test that unscheduled streams include reason and details."""
        # Create a stream with a very large student count that no room can fit
        streams = [
            {
                "id": "stream1",
                "stream_type": "lecture",
                "subject": "Subject 1",
                "instructor": "Instructor 1",
                "language": "каз",
                "groups": ["Group-21", "Group-23"],
                "student_count": 1000,  # Too large for any room
                "hours": {"odd_week": 1, "even_week": 1},
                "sheet": "sheet1",
            },
        ]
        scheduler = Stage1Scheduler(temp_rooms_csv)
        result = scheduler.schedule(streams)

        # Should have one unscheduled stream
        assert result.total_unscheduled == 1
        assert len(result.unscheduled_streams) == 1

        unscheduled = result.unscheduled_streams[0]
        assert unscheduled.stream_id == "stream1"
        assert unscheduled.subject == "Subject 1"
        assert unscheduled.instructor == "Instructor 1"
        assert unscheduled.reason == UnscheduledReason.NO_ROOM_AVAILABLE
        assert "capacity" in unscheduled.details.lower() or "room" in unscheduled.details.lower()

    def test_unscheduled_stream_serialization(self, temp_rooms_csv):
        """Test that unscheduled streams serialize correctly to dict."""
        streams = [
            {
                "id": "stream1",
                "stream_type": "lecture",
                "subject": "Subject 1",
                "instructor": "Instructor 1",
                "language": "каз",
                "groups": ["Group-21", "Group-23"],
                "student_count": 1000,
                "hours": {"odd_week": 1, "even_week": 1},
                "sheet": "sheet1",
            },
        ]
        scheduler = Stage1Scheduler(temp_rooms_csv)
        result = scheduler.schedule(streams)

        data = result.to_dict()
        assert "unscheduled_streams" in data
        assert len(data["unscheduled_streams"]) == 1

        unscheduled_data = data["unscheduled_streams"][0]
        assert "stream_id" in unscheduled_data
        assert "reason" in unscheduled_data
        assert "details" in unscheduled_data
        assert "subject" in unscheduled_data
        assert "instructor" in unscheduled_data
        assert "groups" in unscheduled_data


class TestOverflowDays:
    """Tests for Thursday/Friday overflow day scheduling."""

    def test_uses_overflow_days_when_primary_exhausted(self, temp_rooms_csv):
        """Test that Thu/Fri are used when Mon/Tue/Wed are exhausted."""
        # Create many streams with same instructor to exhaust primary days
        # First shift has 5 slots × 3 days = 15 positions
        # Create 18 streams to force overflow
        # Use all first-year groups (XXX-11) to ensure first shift
        streams = []
        for i in range(18):
            # Use unique group names that all map to year 1 (first shift)
            # Group naming: ABC-11 where ABC is unique per stream
            # Year is determined by first digit of two-digit number (11 = year 1)
            group_prefix = chr(65 + i)  # A, B, C, ...
            streams.append({
                "id": f"stream{i}",
                "stream_type": "lecture",
                "subject": f"Subject {i}",
                "instructor": "Same Instructor",
                "language": "каз",
                # Both groups are year 1 (first digit 1) = first shift
                "groups": [f"{group_prefix}G1-11", f"{group_prefix}G2-11"],
                "student_count": 40,
                "hours": {"odd_week": 1, "even_week": 1},
                "sheet": "sheet1",
            })

        scheduler = Stage1Scheduler(temp_rooms_csv)
        result = scheduler.schedule(streams)

        # Check if any assignments are on Thu or Fri
        overflow_days = {Day.THURSDAY, Day.FRIDAY}
        overflow_assignments = [a for a in result.assignments if a.day in overflow_days]

        # With 18 streams and same instructor, some should overflow to Thu/Fri
        # since first shift has only 5 slots × 3 days = 15 positions
        assert len(overflow_assignments) > 0, "Expected some streams to be scheduled on overflow days"

    def test_primary_days_preferred_over_overflow(self, temp_rooms_csv, sample_streams):
        """Test that Mon/Tue/Wed are used before Thu/Fri."""
        scheduler = Stage1Scheduler(temp_rooms_csv)
        result = scheduler.schedule(sample_streams)

        primary_days = {Day.MONDAY, Day.TUESDAY, Day.WEDNESDAY}
        for assignment in result.assignments:
            # With only 2 streams, all should fit on primary days
            assert assignment.day in primary_days


class TestFlexibleScheduling:
    """Tests for flexible day scheduling (e.g., Physical Education)."""

    def test_flexible_subject_can_use_all_weekdays(self, temp_rooms_csv):
        """Test that flexible subjects can be scheduled on any weekday (Mon-Fri)."""
        # Create streams that exhaust Mon/Tue/Wed slots with same instructor
        # to force flexible subject to use Thu/Fri
        flexible_subject = FLEXIBLE_SCHEDULE_SUBJECTS[0]  # "Дене шынықтыру"
        streams = []

        # First, fill primary days with regular subjects (same instructor limits slots)
        for i in range(15):  # First shift: 5 slots × 3 days = 15 positions
            group_prefix = chr(65 + i)
            streams.append({
                "id": f"regular{i}",
                "stream_type": "lecture",
                "subject": f"Regular Subject {i}",
                "instructor": "Same Instructor",
                "language": "каз",
                "groups": [f"{group_prefix}G1-11", f"{group_prefix}G2-11"],
                "student_count": 40,
                "hours": {"odd_week": 1, "even_week": 1},
                "sheet": "sheet1",
            })

        # Add flexible subject stream
        streams.append({
            "id": "flexible1",
            "stream_type": "lecture",
            "subject": flexible_subject,
            "instructor": "Same Instructor",
            "language": "каз",
            "groups": ["ZZ1-11", "ZZ2-11"],
            "student_count": 40,
            "hours": {"odd_week": 1, "even_week": 1},
            "sheet": "sheet1",
        })

        scheduler = Stage1Scheduler(temp_rooms_csv)
        result = scheduler.schedule(streams)

        # Find assignments for flexible subject
        flexible_assignments = [
            a for a in result.assignments
            if a.subject == flexible_subject
        ]

        # Flexible subject should be scheduled (not unscheduled)
        assert len(flexible_assignments) > 0, "Flexible subject should be scheduled"

        # All weekdays are valid for flexible subjects
        all_weekdays = {Day.MONDAY, Day.TUESDAY, Day.WEDNESDAY, Day.THURSDAY, Day.FRIDAY}
        for assignment in flexible_assignments:
            assert assignment.day in all_weekdays

    def test_regular_subjects_prefer_primary_days(self, temp_rooms_csv):
        """Test that regular subjects still prefer Mon/Tue/Wed."""
        streams = [
            {
                "id": "stream1",
                "stream_type": "lecture",
                "subject": "Regular Subject",
                "instructor": "Instructor 1",
                "language": "каз",
                "groups": ["Group-11", "Group-13"],
                "student_count": 50,
                "hours": {"odd_week": 1, "even_week": 1},
                "sheet": "sheet1",
            },
        ]

        scheduler = Stage1Scheduler(temp_rooms_csv)
        result = scheduler.schedule(streams)

        primary_days = {Day.MONDAY, Day.TUESDAY, Day.WEDNESDAY}
        for assignment in result.assignments:
            assert assignment.day in primary_days, "Regular subjects should use primary days"

    def test_flexible_subjects_scheduled_after_regular(self, temp_rooms_csv):
        """Test that flexible subjects are scheduled after regular subjects."""
        flexible_subject = FLEXIBLE_SCHEDULE_SUBJECTS[0]  # "Дене шынықтыру"
        streams = [
            {
                "id": "flexible1",
                "stream_type": "lecture",
                "subject": flexible_subject,
                "instructor": "Instructor A",
                "language": "каз",
                "groups": ["Group-11", "Group-13"],
                "student_count": 50,
                "hours": {"odd_week": 1, "even_week": 1},
                "sheet": "sheet1",
            },
            {
                "id": "regular1",
                "stream_type": "lecture",
                "subject": "Regular Subject",
                "instructor": "Instructor B",
                "language": "каз",
                "groups": ["Group-21", "Group-23"],
                "student_count": 50,
                "hours": {"odd_week": 1, "even_week": 1},
                "sheet": "sheet1",
            },
        ]

        # Test the sorting function directly
        lecture_streams = filter_stage1_lectures(streams)
        sorted_streams = sort_streams_by_priority(lecture_streams)

        # Find indices
        flexible_idx = None
        regular_idx = None
        for i, s in enumerate(sorted_streams):
            if s.subject == flexible_subject:
                flexible_idx = i
            elif s.subject == "Regular Subject":
                regular_idx = i

        assert flexible_idx is not None, "Flexible stream should be in sorted list"
        assert regular_idx is not None, "Regular stream should be in sorted list"
        assert regular_idx < flexible_idx, "Regular subjects should come before flexible"

    def test_is_flexible_subject_method(self, temp_rooms_csv):
        """Test the _is_flexible_subject() method."""
        scheduler = Stage1Scheduler(temp_rooms_csv)

        # Test flexible subject
        assert scheduler._is_flexible_subject("Дене шынықтыру") is True

        # Test regular subject
        assert scheduler._is_flexible_subject("Математика") is False
        assert scheduler._is_flexible_subject("Regular Subject") is False

    def test_get_allowed_days_method(self, temp_rooms_csv):
        """Test the _get_allowed_days() method."""
        scheduler = Stage1Scheduler(temp_rooms_csv)

        # Test flexible subject - all weekdays, no overflow
        flexible_subject = FLEXIBLE_SCHEDULE_SUBJECTS[0]
        primary, overflow = scheduler._get_allowed_days(flexible_subject)
        assert len(primary) == 5  # Mon-Fri
        assert len(overflow) == 0

        # Test regular subject - standard primary + overflow
        primary, overflow = scheduler._get_allowed_days("Regular Subject")
        assert len(primary) == 3  # Mon/Tue/Wed
        assert len(overflow) == 2  # Thu/Fri
