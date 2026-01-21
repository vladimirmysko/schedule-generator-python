"""Tests for Stage1Scheduler class."""

import csv
import tempfile
from pathlib import Path

import pytest

from form1_parser.scheduler.algorithm import Stage1Scheduler, create_scheduler
from form1_parser.scheduler.models import Day


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
            "groups": ["Group-21", "Group-23"],  # Year 1 groups -> First shift
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
            "groups": ["Group-21", "Group-25"],  # Year 1 groups -> First shift
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
