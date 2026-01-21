"""Tests for RoomManager class."""

import csv
import tempfile
from pathlib import Path

import pytest

from form1_parser.scheduler.constants import Shift
from form1_parser.scheduler.models import Day, LectureStream
from form1_parser.scheduler.rooms import RoomManager


@pytest.fixture
def temp_rooms_csv():
    """Create a temporary rooms.csv file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        writer = csv.DictWriter(f, fieldnames=["name", "capacity", "address", "is_special"])
        writer.writeheader()
        writer.writerows(
            [
                {"name": "А-1", "capacity": "50", "address": "Address 1", "is_special": ""},
                {"name": "А-2", "capacity": "100", "address": "Address 1", "is_special": ""},
                {"name": "А-3", "capacity": "150", "address": "Address 1", "is_special": ""},
                {"name": "Special", "capacity": "200", "address": "Address 2", "is_special": "true"},
                {"name": "Neutral-1", "capacity": "100", "address": "Address 3", "is_special": ""},
            ]
        )
        return Path(f.name)


@pytest.fixture
def sample_stream():
    """Create a sample lecture stream for testing."""
    return LectureStream(
        id="test_stream",
        subject="Test Subject",
        instructor="Test Instructor",
        language="каз",
        groups=["Group1", "Group2"],
        student_count=75,
        hours_odd_week=1,
        hours_even_week=1,
        shift=Shift.FIRST,
        sheet="sheet1",
    )


class TestRoomManager:
    """Tests for RoomManager class."""

    def test_loads_rooms_from_csv(self, temp_rooms_csv):
        manager = RoomManager(temp_rooms_csv)
        assert len(manager.rooms) == 5

    def test_find_room_by_capacity(self, temp_rooms_csv, sample_stream):
        manager = RoomManager(temp_rooms_csv)
        room = manager.find_room(sample_stream, Day.MONDAY, 1)
        # Should find А-2 (100 capacity) as smallest room >= 75 students
        assert room is not None
        assert room.name == "А-2"

    def test_find_room_excludes_special_by_default(self, temp_rooms_csv):
        manager = RoomManager(temp_rooms_csv)
        stream = LectureStream(
            id="test_stream",
            subject="Test Subject",
            instructor="Test Instructor",
            language="каз",
            groups=["Group1", "Group2"],
            student_count=190,  # Only Special room (200) fits, even with buffer
            hours_odd_week=1,
            hours_even_week=1,
            shift=Shift.FIRST,
            sheet="sheet1",
        )
        room = manager.find_room(stream, Day.MONDAY, 1)
        # Should return None because Special room is excluded and no other fits
        # Buffer for 190 is ~20% = 38, so min_required = 190 - 38 = 152 > 150
        assert room is None

    def test_room_reservation(self, temp_rooms_csv, sample_stream):
        manager = RoomManager(temp_rooms_csv)
        room = manager.find_room(sample_stream, Day.MONDAY, 1)
        assert room is not None
        manager.reserve_room(room, Day.MONDAY, 1)

        # Same room should not be available at same time
        assert not manager.is_room_available(room.name, Day.MONDAY, 1)
        # But should be available at different time
        assert manager.is_room_available(room.name, Day.MONDAY, 2)
        assert manager.is_room_available(room.name, Day.TUESDAY, 1)

    def test_find_room_skips_occupied(self, temp_rooms_csv, sample_stream):
        manager = RoomManager(temp_rooms_csv)

        # Reserve А-2 (100 capacity)
        room1 = manager.find_room(sample_stream, Day.MONDAY, 1)
        manager.reserve_room(room1, Day.MONDAY, 1)

        # Next search should find Neutral-1 (100 capacity, same as А-2, smallest available)
        room2 = manager.find_room(sample_stream, Day.MONDAY, 1)
        assert room2 is not None
        assert room2.name == "Neutral-1"

    def test_get_room_by_name(self, temp_rooms_csv):
        manager = RoomManager(temp_rooms_csv)
        room = manager.get_room_by_name("А-1")
        assert room is not None
        assert room.capacity == 50

    def test_get_room_by_name_with_address(self, temp_rooms_csv):
        manager = RoomManager(temp_rooms_csv)
        room = manager.get_room_by_name("А-1", "Address 1")
        assert room is not None

        room = manager.get_room_by_name("А-1", "Wrong Address")
        assert room is None


class TestRoomManagerCapacityBuffer:
    """Tests for capacity buffer calculations."""

    def test_buffer_small_stream(self, temp_rooms_csv):
        manager = RoomManager(temp_rooms_csv)
        # 50% buffer for small streams (<30)
        buffer = manager._calculate_buffer(20)
        assert buffer == 10  # 50% of 20

    def test_buffer_large_stream(self, temp_rooms_csv):
        manager = RoomManager(temp_rooms_csv)
        # 20% buffer for large streams (>100)
        buffer = manager._calculate_buffer(100)
        assert buffer == 20  # 20% of 100

    def test_buffer_medium_stream(self, temp_rooms_csv):
        manager = RoomManager(temp_rooms_csv)
        # Linear interpolation between 50% at 30 and 20% at 100
        buffer = manager._calculate_buffer(65)
        # At 65, ratio = (65-30)/70 = 0.5, buffer_pct = 0.5 - 0.5*0.3 = 0.35
        assert buffer == 22  # int(65 * 0.35)


class TestRoomManagerSubjectRooms:
    """Tests for subject-specific room handling."""

    def test_subject_rooms_priority(self, temp_rooms_csv):
        subject_rooms = {
            "Test Subject": {
                "lecture": [
                    {"address": "Address 1", "room": "А-1"},
                ]
            }
        }
        manager = RoomManager(temp_rooms_csv, subject_rooms=subject_rooms)

        stream = LectureStream(
            id="test_stream",
            subject="Test Subject",
            instructor="Test Instructor",
            language="каз",
            groups=["Group1", "Group2"],
            student_count=40,  # А-2 would normally fit better
            hours_odd_week=1,
            hours_even_week=1,
            shift=Shift.FIRST,
            sheet="sheet1",
        )

        room = manager.find_room(stream, Day.MONDAY, 1)
        # Should prefer А-1 from subject_rooms even though capacity is smaller
        assert room is not None
        assert room.name == "А-1"


class TestRoomManagerInstructorRooms:
    """Tests for instructor-specific room handling."""

    def test_instructor_rooms_priority(self, temp_rooms_csv):
        instructor_rooms = {
            "Test Instructor": {
                "lecture": [
                    {"address": "Address 1", "room": "А-3"},
                ]
            }
        }
        manager = RoomManager(temp_rooms_csv, instructor_rooms=instructor_rooms)

        stream = LectureStream(
            id="test_stream",
            subject="Unknown Subject",
            instructor="Test Instructor",
            language="каз",
            groups=["Group1", "Group2"],
            student_count=75,
            hours_odd_week=1,
            hours_even_week=1,
            shift=Shift.FIRST,
            sheet="sheet1",
        )

        room = manager.find_room(stream, Day.MONDAY, 1)
        # Should prefer А-3 from instructor_rooms
        assert room is not None
        assert room.name == "А-3"

    def test_clean_instructor_name(self, temp_rooms_csv):
        manager = RoomManager(temp_rooms_csv)
        assert manager._clean_instructor_name("а.о.Иванов И.И.") == "Иванов И.И."
        assert manager._clean_instructor_name("с.п.Петров П.П.") == "Петров П.П."


class TestRoomManagerGroupBuildings:
    """Tests for group-building preferences."""

    def test_group_building_preference_applied(self, temp_rooms_csv):
        """Test that group building preferences are applied."""
        group_buildings = {
            "АРХ": {
                "addresses": [{"address": "Address 1"}],
            }
        }
        manager = RoomManager(temp_rooms_csv, group_buildings=group_buildings)

        # АРХ groups should prefer Address 1
        stream = LectureStream(
            id="test_stream",
            subject="Unknown Subject",
            instructor="Unknown Instructor",
            language="каз",
            groups=["АРХ-23 О", "АРХ-25 О"],
            student_count=75,
            hours_odd_week=1,
            hours_even_week=1,
            shift=Shift.FIRST,
            sheet="sheet1",
        )

        room = manager.find_room(stream, Day.MONDAY, 1)
        assert room is not None
        assert room.address == "Address 1"

    def test_group_building_unknown_specialty_no_preference(self, temp_rooms_csv):
        """Test that unknown specialties don't get building preference."""
        group_buildings = {
            "АРХ": {
                "addresses": [{"address": "Address 2"}],
            }
        }
        manager = RoomManager(temp_rooms_csv, group_buildings=group_buildings)

        # UNKNOWN specialty should NOT get Address 2 preference
        stream = LectureStream(
            id="test_stream",
            subject="Unknown Subject",
            instructor="Unknown Instructor",
            language="каз",
            groups=["UNKNOWN-21 О"],
            student_count=75,
            hours_odd_week=1,
            hours_even_week=1,
            shift=Shift.FIRST,
            sheet="sheet1",
        )

        room = manager.find_room(stream, Day.MONDAY, 1)
        assert room is not None
        # Should fall through to general pool (Address 1 has more rooms)
        assert room.address == "Address 1"

    def test_group_building_specific_rooms(self, temp_rooms_csv):
        """Test that specific room restrictions within building are respected."""
        group_buildings = {
            "ВЕТ": {
                "addresses": [{"address": "Address 1", "rooms": ["А-1"]}],
            }
        }
        manager = RoomManager(temp_rooms_csv, group_buildings=group_buildings)

        # ВЕТ should only get А-1
        stream = LectureStream(
            id="test_stream",
            subject="Unknown Subject",
            instructor="Unknown Instructor",
            language="каз",
            groups=["ВЕТ-23 О"],
            student_count=40,  # Fits in А-1 (50)
            hours_odd_week=1,
            hours_even_week=1,
            shift=Shift.FIRST,
            sheet="sheet1",
        )

        room = manager.find_room(stream, Day.MONDAY, 1)
        assert room is not None
        assert room.name == "А-1"

    def test_subject_rooms_override_group_buildings(self, temp_rooms_csv):
        """Test that subject rooms take priority over group building preferences."""
        subject_rooms = {
            "Химия": {
                "locations": [{"address": "Address 2", "room": "Special"}],
            }
        }
        group_buildings = {
            "АРХ": {
                "addresses": [{"address": "Address 1"}],
            }
        }
        manager = RoomManager(
            temp_rooms_csv,
            subject_rooms=subject_rooms,
            group_buildings=group_buildings,
        )

        # АРХ taking Химия should get Address 2 (subject priority)
        stream = LectureStream(
            id="test_stream",
            subject="Химия",
            instructor="Unknown Instructor",
            language="каз",
            groups=["АРХ-23 О"],
            student_count=75,
            hours_odd_week=1,
            hours_even_week=1,
            shift=Shift.FIRST,
            sheet="sheet1",
        )

        room = manager.find_room(stream, Day.MONDAY, 1)
        assert room is not None
        assert room.address == "Address 2"  # Subject priority wins

    def test_mixed_specialties_no_preference(self, temp_rooms_csv):
        """Test that mixed specialties don't get building preference and can't use reserved buildings."""
        group_buildings = {
            "ЮР": {
                "addresses": [{"address": "Address 2"}],
            },
            "АРХ": {
                "addresses": [{"address": "Address 1"}],
            },
        }
        manager = RoomManager(temp_rooms_csv, group_buildings=group_buildings)

        # Mixed ЮР and АРХ groups should NOT get building preference
        # AND cannot use buildings reserved for other specialties
        stream = LectureStream(
            id="test_stream",
            subject="Unknown Subject",
            instructor="Unknown Instructor",
            language="каз",
            groups=["ЮР-21 О /у/", "ЮР-23 О /у/", "АРХ-21 О"],  # Mixed specialties
            student_count=75,
            hours_odd_week=1,
            hours_even_week=1,
            shift=Shift.FIRST,
            sheet="sheet1",
        )

        room = manager.find_room(stream, Day.MONDAY, 1)
        assert room is not None
        # Should fall through to general pool - only neutral Address 3 is available
        # (Address 1 reserved for АРХ only, Address 2 reserved for ЮР only)
        assert room.address == "Address 3"

    def test_parse_group_specialty(self, temp_rooms_csv):
        """Test specialty parsing from group names."""
        manager = RoomManager(temp_rooms_csv)
        assert manager._parse_group_specialty("АРХ-21 О") == "АРХ"
        assert manager._parse_group_specialty("ВТИС-23 О") == "ВТИС"
        assert manager._parse_group_specialty("ЮР-15 О /у/") == "ЮР"

    def test_parse_group_year(self, temp_rooms_csv):
        """Test year parsing from group names."""
        manager = RoomManager(temp_rooms_csv)
        assert manager._parse_group_year("АРХ-21 О") == 1
        assert manager._parse_group_year("АРХ-23 О") == 2
        assert manager._parse_group_year("АРХ-25 О") == 3
        assert manager._parse_group_year("АРХ-27 О") == 4
        assert manager._parse_group_year("АРХ-29 О") == 5


class TestRoomManagerExclusiveBuildings:
    """Tests for exclusive building constraint."""

    def test_other_specialty_cannot_use_reserved_building(self, temp_rooms_csv):
        """Test that specialties cannot use buildings reserved for others."""
        group_buildings = {
            "ВЕТ": {
                "addresses": [{"address": "Address 1"}],
            },
        }
        manager = RoomManager(temp_rooms_csv, group_buildings=group_buildings)

        # ЮР groups should NOT be able to use Address 1 (reserved for ВЕТ)
        stream = LectureStream(
            id="test_stream",
            subject="Unknown Subject",
            instructor="Unknown Instructor",
            language="каз",
            groups=["ЮР-21 О /у/", "ЮР-23 О /у/"],
            student_count=75,
            hours_odd_week=1,
            hours_even_week=1,
            shift=Shift.FIRST,
            sheet="sheet1",
        )

        room = manager.find_room(stream, Day.MONDAY, 1)
        assert room is not None
        # Should use neutral Address 3 instead of reserved Address 1
        assert room.address == "Address 3"

    def test_correct_specialty_can_use_reserved_building(self, temp_rooms_csv):
        """Test that the designated specialty can use their reserved building."""
        group_buildings = {
            "ВЕТ": {
                "addresses": [{"address": "Address 1"}],
            },
        }
        manager = RoomManager(temp_rooms_csv, group_buildings=group_buildings)

        # ВЕТ groups CAN use Address 1 (reserved for them)
        stream = LectureStream(
            id="test_stream",
            subject="Unknown Subject",
            instructor="Unknown Instructor",
            language="каз",
            groups=["ВЕТ-21 О", "ВЕТ-23 О"],
            student_count=75,
            hours_odd_week=1,
            hours_even_week=1,
            shift=Shift.FIRST,
            sheet="sheet1",
        )

        room = manager.find_room(stream, Day.MONDAY, 1)
        assert room is not None
        # Should get Address 1 (their preferred building)
        assert room.address == "Address 1"

    def test_is_address_allowed_for_groups(self, temp_rooms_csv):
        """Test the _is_address_allowed_for_groups helper method."""
        group_buildings = {
            "ВЕТ": {
                "addresses": [{"address": "Address 1"}],
            },
            "ЮР": {
                "addresses": [{"address": "Address 2"}],
            },
        }
        manager = RoomManager(temp_rooms_csv, group_buildings=group_buildings)

        # Reserved address - only allowed specialty can use it
        assert manager._is_address_allowed_for_groups("Address 1", ["ВЕТ-21 О"]) is True
        assert manager._is_address_allowed_for_groups("Address 1", ["ЮР-21 О"]) is False
        assert manager._is_address_allowed_for_groups("Address 2", ["ЮР-21 О"]) is True
        assert manager._is_address_allowed_for_groups("Address 2", ["ВЕТ-21 О"]) is False

        # Mixed groups - need ALL specialties to be allowed
        assert manager._is_address_allowed_for_groups("Address 1", ["ВЕТ-21 О", "ЮР-21 О"]) is False

        # Non-reserved address - anyone can use it
        assert manager._is_address_allowed_for_groups("Address 3", ["ВЕТ-21 О"]) is True
        assert manager._is_address_allowed_for_groups("Address 3", ["ЮР-21 О"]) is True
        assert manager._is_address_allowed_for_groups("Address 3", ["UNKNOWN-21 О"]) is True
