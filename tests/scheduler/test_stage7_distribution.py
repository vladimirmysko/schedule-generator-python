"""Tests for Stage 7 weekday distribution adjustments."""

import csv
import tempfile
from collections import defaultdict
from pathlib import Path

import pytest

from form1_parser.scheduler.conflicts import ConflictTracker
from form1_parser.scheduler.models import Day
from form1_parser.scheduler.rooms import RoomManager
from form1_parser.scheduler.stage7 import Stage7Scheduler


@pytest.fixture
def temp_rooms_csv() -> Path:
    """Create a temporary rooms.csv file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["name", "capacity", "address", "is_special"]
        )
        writer.writeheader()
        writer.writerow(
            {
                "name": "Room-1",
                "capacity": "120",
                "address": "Main Building",
                "is_special": "",
            }
        )
        return Path(handle.name)


def _make_assignment(
    stream_id: str,
    subject: str,
    instructor: str,
    groups: list[str],
    day: str,
    slot: int,
) -> dict:
    return {
        "stream_id": stream_id,
        "subject": subject,
        "instructor": instructor,
        "groups": groups,
        "student_count": 25,
        "day": day,
        "slot": slot,
        "room": "Room-1",
        "room_address": "Main Building",
        "week_type": "both",
        "stream_type": "practical",
    }


def _build_streams(assignments: list[dict]) -> list[dict]:
    streams = []
    for assignment in assignments:
        streams.append(
            {
                "id": assignment["stream_id"],
                "subject": assignment["subject"],
                "stream_type": assignment["stream_type"],
                "instructor": assignment["instructor"],
                "groups": assignment["groups"],
                "student_count": assignment["student_count"],
                "hours": {"odd_week": 1, "even_week": 1},
                "is_subgroup": False,
                "is_implicit_subgroup": False,
            }
        )
    return streams


def _collect_group_days(assignments, group: str) -> dict[str, int]:
    day_counts: dict[str, int] = defaultdict(int)
    for assignment in assignments:
        if group not in assignment.groups:
            continue
        day_counts[assignment.day.value] += 1
    return day_counts


def test_stage7_spreads_year4_across_weekdays(temp_rooms_csv):
    groups = ["TEST-41 O"]
    assignments = [
        _make_assignment("s1", "Subject A", "Instructor A", groups, "monday", 6),
        _make_assignment("s2", "Subject A", "Instructor A", groups, "monday", 7),
        _make_assignment("s3", "Subject A", "Instructor A", groups, "monday", 8),
        _make_assignment("s4", "Subject A", "Instructor A", groups, "monday", 9),
        _make_assignment("s5", "Subject A", "Instructor A", groups, "tuesday", 6),
        _make_assignment("s6", "Subject A", "Instructor A", groups, "tuesday", 7),
    ]

    scheduler = Stage7Scheduler(
        room_manager=RoomManager(temp_rooms_csv),
        conflict_tracker=ConflictTracker(),
    )
    result = scheduler.schedule(_build_streams(assignments), assignments, [])

    day_counts = _collect_group_days(result.assignments, "TEST-41 O")
    for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]:
        assert day_counts.get(day, 0) > 0


def test_stage7_allows_year4_multigroup_moves(temp_rooms_csv):
    groups = ["TEST-41 O", "TEST-42 O"]
    assignments = [
        _make_assignment("m1", "Subject B", "Instructor B", groups, "monday", 6),
        _make_assignment("m2", "Subject B", "Instructor B", groups, "monday", 7),
        _make_assignment("m3", "Subject B", "Instructor B", groups, "tuesday", 6),
    ]

    scheduler = Stage7Scheduler(
        room_manager=RoomManager(temp_rooms_csv),
        conflict_tracker=ConflictTracker(),
    )
    result = scheduler.schedule(_build_streams(assignments), assignments, [])

    days_used = {assignment.day for assignment in result.assignments}
    assert any(day in {Day.WEDNESDAY, Day.THURSDAY, Day.FRIDAY} for day in days_used)
