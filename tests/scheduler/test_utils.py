"""Tests for scheduler utility functions."""

import pytest

from form1_parser.scheduler.constants import Shift
from form1_parser.scheduler.utils import (
    clean_instructor_name,
    determine_shift,
    filter_stage1_lectures,
    get_shift_for_groups,
    parse_group_year,
    parse_specialty_code,
    sort_streams_by_priority,
)


class TestParseGroupYear:
    """Tests for parse_group_year function."""

    def test_year_1_from_11(self):
        assert parse_group_year("АРХ-11 О") == 1

    def test_year_1_from_15(self):
        assert parse_group_year("АРХ-15 О") == 1

    def test_year_2_from_21(self):
        assert parse_group_year("АРХ-21 О") == 2

    def test_year_2_from_23(self):
        assert parse_group_year("СТР-23 О") == 2

    def test_year_3_from_31(self):
        assert parse_group_year("НД-31 О") == 3

    def test_year_3_from_35(self):
        assert parse_group_year("НД-35 О") == 3

    def test_year_4_from_41(self):
        assert parse_group_year("ЭЛ-41 О") == 4

    def test_year_5_from_51(self):
        assert parse_group_year("ТТТ-51 О") == 5

    def test_no_number_returns_none(self):
        assert parse_group_year("АРХ О") is None


class TestParseSpecialtyCode:
    """Tests for parse_specialty_code function."""

    def test_simple_code(self):
        assert parse_specialty_code("АРХ-21 О") == "АРХ"

    def test_long_code(self):
        assert parse_specialty_code("ВТИС-21 О") == "ВТИС"

    def test_empty_string(self):
        assert parse_specialty_code("") is None


class TestDetermineShift:
    """Tests for determine_shift function."""

    def test_first_year_first_shift(self):
        assert determine_shift(1) == Shift.FIRST

    def test_second_year_second_shift(self):
        assert determine_shift(2) == Shift.SECOND

    def test_third_year_first_shift(self):
        assert determine_shift(3) == Shift.FIRST

    def test_fourth_year_second_shift(self):
        assert determine_shift(4) == Shift.SECOND

    def test_fifth_year_second_shift(self):
        assert determine_shift(5) == Shift.SECOND

    def test_none_defaults_to_second_shift(self):
        assert determine_shift(None) == Shift.SECOND


class TestGetShiftForGroups:
    """Tests for get_shift_for_groups function."""

    def test_first_year_groups_first_shift(self):
        groups = ["АРХ-11 О", "СТР-11 О"]
        assert get_shift_for_groups(groups) == Shift.FIRST

    def test_second_year_groups_second_shift(self):
        groups = ["АРХ-21 О", "СТР-21 О"]
        assert get_shift_for_groups(groups) == Shift.SECOND

    def test_third_year_groups_first_shift(self):
        groups = ["АРХ-31 О", "СТР-31 О"]
        assert get_shift_for_groups(groups) == Shift.FIRST

    def test_empty_groups_second_shift(self):
        assert get_shift_for_groups([]) == Shift.SECOND


class TestCleanInstructorName:
    """Tests for clean_instructor_name function."""

    def test_removes_ao_prefix(self):
        assert clean_instructor_name("а.о.Уахасов Қ.С.") == "Уахасов Қ.С."

    def test_removes_sp_prefix(self):
        assert clean_instructor_name("с.п.Шалаев Б.Б.") == "Шалаев Б.Б."

    def test_removes_ao_with_space(self):
        assert clean_instructor_name("а.о. Утебалиев М.М.") == "Утебалиев М.М."

    def test_no_prefix(self):
        assert clean_instructor_name("Иванов И.И.") == "Иванов И.И."


class TestFilterStage1Lectures:
    """Tests for filter_stage1_lectures function."""

    def test_filters_lectures_with_2_plus_groups(self):
        streams = [
            {
                "id": "stream1",
                "stream_type": "lecture",
                "subject": "Subject 1",
                "instructor": "Instructor 1",
                "language": "каз",
                "groups": ["Group1", "Group2"],
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
                "groups": ["Group1"],  # Only 1 group - should be filtered out
                "student_count": 25,
                "hours": {"odd_week": 1, "even_week": 1},
                "sheet": "sheet1",
            },
        ]
        result = filter_stage1_lectures(streams)
        assert len(result) == 1
        assert result[0].id == "stream1"

    def test_filters_out_non_lectures(self):
        streams = [
            {
                "id": "stream1",
                "stream_type": "practical",  # Not a lecture
                "subject": "Subject 1",
                "instructor": "Instructor 1",
                "language": "каз",
                "groups": ["Group1", "Group2"],
                "student_count": 50,
                "hours": {"odd_week": 1, "even_week": 1},
                "sheet": "sheet1",
            },
        ]
        result = filter_stage1_lectures(streams)
        assert len(result) == 0


class TestSortStreamsByPriority:
    """Tests for sort_streams_by_priority function."""

    def test_sorts_by_student_count(self):
        from form1_parser.scheduler.models import LectureStream, StreamType

        streams = [
            LectureStream(
                id="s1",
                subject="S1",
                stream_type=StreamType.LECTURE,
                instructor="I1",
                language="каз",
                groups=["G1", "G2"],
                student_count=50,  # Less students
                hours_odd=1,
                hours_even=1,
                sheet="sheet1",
            ),
            LectureStream(
                id="s2",
                subject="S2",
                stream_type=StreamType.LECTURE,
                instructor="I2",
                language="каз",
                groups=["G3", "G4"],
                student_count=100,  # More students → higher priority
                hours_odd=1,
                hours_even=1,
                sheet="sheet1",
            ),
        ]

        result = sort_streams_by_priority(streams)

        # s2 should come first (more students)
        assert result[0].id == "s2"
        assert result[1].id == "s1"

    def test_sorts_by_hours_when_same_student_count(self):
        from form1_parser.scheduler.models import LectureStream, StreamType

        streams = [
            LectureStream(
                id="s1",
                subject="S1",
                stream_type=StreamType.LECTURE,
                instructor="I1",
                language="каз",
                groups=["G1", "G2"],
                student_count=100,  # Same
                hours_odd=1,
                hours_even=1,  # Less hours
                sheet="sheet1",
            ),
            LectureStream(
                id="s2",
                subject="S2",
                stream_type=StreamType.LECTURE,
                instructor="I2",
                language="каз",
                groups=["G3", "G4"],
                student_count=100,  # Same
                hours_odd=2,
                hours_even=2,  # More hours → higher priority
                sheet="sheet1",
            ),
        ]

        result = sort_streams_by_priority(streams)

        # s2 should come first (more hours)
        assert result[0].id == "s2"
        assert result[1].id == "s1"

    def test_flexible_subjects_sorted_last(self):
        from form1_parser.scheduler.models import LectureStream, StreamType

        streams = [
            LectureStream(
                id="s1",
                subject="Дене шынықтыру",  # PE - flexible subject
                stream_type=StreamType.LECTURE,
                instructor="I1",
                language="каз",
                groups=["G1", "G2"],
                student_count=100,
                hours_odd=1,
                hours_even=1,
                sheet="sheet1",
            ),
            LectureStream(
                id="s2",
                subject="Математика",  # Regular subject
                stream_type=StreamType.LECTURE,
                instructor="I2",
                language="каз",
                groups=["G3", "G4"],
                student_count=50,  # Less students but non-flexible
                hours_odd=1,
                hours_even=1,
                sheet="sheet1",
            ),
        ]

        result = sort_streams_by_priority(streams)

        # s2 should come first (non-flexible)
        assert result[0].id == "s2"
        assert result[1].id == "s1"
