"""Tests for scheduler utility functions."""

import pytest

from form1_parser.scheduler.constants import Shift
from form1_parser.scheduler.utils import (
    clean_instructor_name,
    determine_shift,
    filter_stage1_lectures,
    parse_group_year,
    parse_specialty_code,
    sort_streams_by_priority,
)


class TestParseGroupYear:
    """Tests for parse_group_year function."""

    def test_year_1_from_21(self):
        assert parse_group_year("АРХ-21 О") == 1

    def test_year_2_from_23(self):
        assert parse_group_year("СТР-23 О") == 2

    def test_year_3_from_25(self):
        assert parse_group_year("НД-25 О") == 3

    def test_year_4_from_27(self):
        assert parse_group_year("ЭЛ-27 О") == 4

    def test_year_5_from_29(self):
        assert parse_group_year("ТТТ-29 О") == 5

    def test_year_1_from_11(self):
        assert parse_group_year("АРХ-11 О") == 1

    def test_no_number_defaults_to_1(self):
        assert parse_group_year("АРХ О") == 1


class TestParseSpecialtyCode:
    """Tests for parse_specialty_code function."""

    def test_simple_code(self):
        assert parse_specialty_code("АРХ-21 О") == "АРХ"

    def test_long_code(self):
        assert parse_specialty_code("ВТИС-21 О") == "ВТИС"

    def test_english_code(self):
        assert parse_specialty_code("IT-21 О") == "IT"

    def test_empty_string(self):
        assert parse_specialty_code("") == ""


class TestDetermineShift:
    """Tests for determine_shift function."""

    def test_first_year_first_shift(self):
        groups = ["АРХ-21 О", "СТР-21 О"]
        assert determine_shift(groups) == Shift.FIRST

    def test_second_year_second_shift(self):
        groups = ["АРХ-23 О", "СТР-23 О"]
        assert determine_shift(groups) == Shift.SECOND

    def test_third_year_first_shift(self):
        groups = ["АРХ-25 О", "СТР-25 О"]
        assert determine_shift(groups) == Shift.FIRST

    def test_fourth_year_second_shift(self):
        groups = ["АРХ-27 О", "СТР-27 О"]
        assert determine_shift(groups) == Shift.SECOND

    def test_fifth_year_second_shift(self):
        groups = ["АРХ-29 О", "СТР-29 О"]
        assert determine_shift(groups) == Shift.SECOND

    def test_empty_groups_first_shift(self):
        assert determine_shift([]) == Shift.FIRST


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

    def test_filters_out_zero_hours(self):
        streams = [
            {
                "id": "stream1",
                "stream_type": "lecture",
                "subject": "Subject 1",
                "instructor": "Instructor 1",
                "language": "каз",
                "groups": ["Group1", "Group2"],
                "student_count": 50,
                "hours": {"odd_week": 0, "even_week": 0},  # No hours
                "sheet": "sheet1",
            },
        ]
        result = filter_stage1_lectures(streams)
        assert len(result) == 0


class TestSortStreamsByPriority:
    """Tests for sort_streams_by_priority function."""

    def test_sorts_by_student_count_descending(self):
        from form1_parser.scheduler.models import LectureStream

        streams = [
            LectureStream(
                id="s1",
                subject="S1",
                instructor="I1",
                language="каз",
                groups=["G1", "G2"],
                student_count=50,
                hours_odd_week=1,
                hours_even_week=1,
                shift=Shift.FIRST,
                sheet="sheet1",
            ),
            LectureStream(
                id="s2",
                subject="S2",
                instructor="I2",
                language="каз",
                groups=["G3", "G4"],
                student_count=100,
                hours_odd_week=1,
                hours_even_week=1,
                shift=Shift.FIRST,
                sheet="sheet1",
            ),
            LectureStream(
                id="s3",
                subject="S3",
                instructor="I3",
                language="каз",
                groups=["G5", "G6"],
                student_count=75,
                hours_odd_week=1,
                hours_even_week=1,
                shift=Shift.FIRST,
                sheet="sheet1",
            ),
        ]

        result = sort_streams_by_priority(streams)

        assert result[0].student_count == 100
        assert result[1].student_count == 75
        assert result[2].student_count == 50
