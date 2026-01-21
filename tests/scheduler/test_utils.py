"""Tests for scheduler utility functions."""

import pytest

from form1_parser.scheduler.constants import Shift
from form1_parser.scheduler.utils import (
    build_subject_prac_lab_hours,
    calculate_instructor_available_slots,
    clean_instructor_name,
    determine_shift,
    filter_stage1_lectures,
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
        groups = ["АРХ-11 О", "СТР-11 О"]
        assert determine_shift(groups) == Shift.FIRST

    def test_second_year_second_shift(self):
        groups = ["АРХ-21 О", "СТР-21 О"]
        assert determine_shift(groups) == Shift.SECOND

    def test_third_year_first_shift(self):
        groups = ["АРХ-31 О", "СТР-31 О"]
        assert determine_shift(groups) == Shift.FIRST

    def test_fourth_year_second_shift(self):
        groups = ["АРХ-41 О", "СТР-41 О"]
        assert determine_shift(groups) == Shift.SECOND

    def test_fifth_year_second_shift(self):
        groups = ["АРХ-51 О", "СТР-51 О"]
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


class TestBuildSubjectPracLabHours:
    """Tests for build_subject_prac_lab_hours function."""

    def test_sums_practical_and_lab_hours(self):
        streams = [
            {
                "stream_type": "practical",
                "subject": "Math",
                "hours": {"odd_week": 2, "even_week": 2},
            },
            {
                "stream_type": "lab",
                "subject": "Math",
                "hours": {"odd_week": 1, "even_week": 1},
            },
            {
                "stream_type": "lecture",
                "subject": "Math",
                "hours": {"odd_week": 2, "even_week": 2},
            },
        ]
        result = build_subject_prac_lab_hours(streams)
        # Only practical (4) + lab (2) = 6; lecture not counted
        assert result["Math"] == 6

    def test_multiple_subjects(self):
        streams = [
            {
                "stream_type": "practical",
                "subject": "Math",
                "hours": {"odd_week": 2, "even_week": 2},
            },
            {
                "stream_type": "practical",
                "subject": "Physics",
                "hours": {"odd_week": 1, "even_week": 1},
            },
        ]
        result = build_subject_prac_lab_hours(streams)
        assert result["Math"] == 4
        assert result["Physics"] == 2

    def test_empty_streams(self):
        result = build_subject_prac_lab_hours([])
        assert result == {}

    def test_no_practical_or_lab(self):
        streams = [
            {
                "stream_type": "lecture",
                "subject": "Math",
                "hours": {"odd_week": 2, "even_week": 2},
            },
        ]
        result = build_subject_prac_lab_hours(streams)
        assert result == {}


class TestCalculateInstructorAvailableSlots:
    """Tests for calculate_instructor_available_slots function."""

    def test_full_availability_first_shift(self):
        # No availability restrictions → all slots available
        # First shift: 5 slots × 3 days = 15
        result = calculate_instructor_available_slots(
            "Иванов И.И.", Shift.FIRST, None
        )
        assert result == 15

    def test_full_availability_second_shift(self):
        # Second shift: 8 slots × 3 days = 24
        result = calculate_instructor_available_slots(
            "Иванов И.И.", Shift.SECOND, None
        )
        assert result == 24

    def test_with_unavailability(self):
        availability = [
            {
                "name": "Иванов И.И.",
                "weekly_unavailable": {
                    "monday": ["09:00", "10:00"],  # 2 first-shift slots on Monday
                    "tuesday": ["09:00"],  # 1 first-shift slot on Tuesday
                },
            }
        ]
        # 15 total - 3 unavailable = 12
        result = calculate_instructor_available_slots(
            "Иванов И.И.", Shift.FIRST, availability
        )
        assert result == 12

    def test_cleans_instructor_prefix(self):
        availability = [
            {
                "name": "Иванов И.И.",
                "weekly_unavailable": {
                    "monday": ["09:00"],
                },
            }
        ]
        # Should match after cleaning "а.о." prefix
        result = calculate_instructor_available_slots(
            "а.о.Иванов И.И.", Shift.FIRST, availability
        )
        assert result == 14  # 15 - 1 = 14

    def test_instructor_not_in_availability_list(self):
        availability = [
            {
                "name": "Петров П.П.",
                "weekly_unavailable": {"monday": ["09:00"]},
            }
        ]
        # Instructor not found → full availability
        result = calculate_instructor_available_slots(
            "Иванов И.И.", Shift.FIRST, availability
        )
        assert result == 15

    def test_only_counts_shift_relevant_times(self):
        availability = [
            {
                "name": "Иванов И.И.",
                "weekly_unavailable": {
                    "monday": ["09:00", "14:00"],  # 09:00 is first shift, 14:00 is second
                },
            }
        ]
        # First shift: only 09:00 counts
        result = calculate_instructor_available_slots(
            "Иванов И.И.", Shift.FIRST, availability
        )
        assert result == 14  # 15 - 1 = 14


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

    def test_populates_subject_prac_lab_hours(self):
        streams = [
            {
                "id": "stream1",
                "stream_type": "lecture",
                "subject": "Math",
                "instructor": "Instructor 1",
                "language": "каз",
                "groups": ["АРХ-21 О", "СТР-21 О"],
                "student_count": 50,
                "hours": {"odd_week": 1, "even_week": 1},
                "sheet": "sheet1",
            },
            {
                "id": "stream2",
                "stream_type": "practical",
                "subject": "Math",
                "instructor": "Instructor 2",
                "language": "каз",
                "groups": ["АРХ-21 О"],
                "student_count": 25,
                "hours": {"odd_week": 2, "even_week": 2},
                "sheet": "sheet1",
            },
        ]
        result = filter_stage1_lectures(streams)
        assert len(result) == 1
        assert result[0].subject_prac_lab_hours == 4  # 2 + 2 from practical

    def test_populates_instructor_available_slots(self):
        streams = [
            {
                "id": "stream1",
                "stream_type": "lecture",
                "subject": "Math",
                "instructor": "Instructor 1",
                "language": "каз",
                "groups": ["АРХ-11 О", "СТР-11 О"],  # 1st year = first shift
                "student_count": 50,
                "hours": {"odd_week": 1, "even_week": 1},
                "sheet": "sheet1",
            },
        ]
        availability = [
            {
                "name": "Instructor 1",
                "weekly_unavailable": {
                    "monday": ["09:00", "10:00"],
                },
            }
        ]
        result = filter_stage1_lectures(streams, instructor_availability=availability)
        assert len(result) == 1
        assert result[0].instructor_available_slots == 13  # 15 - 2 = 13


class TestSortStreamsByPriority:
    """Tests for sort_streams_by_priority function."""

    def test_sorts_by_instructor_available_slots_first(self):
        from form1_parser.scheduler.models import LectureStream

        streams = [
            LectureStream(
                id="s1",
                subject="S1",
                instructor="I1",
                language="каз",
                groups=["G1", "G2"],
                student_count=100,
                hours_odd_week=1,
                hours_even_week=1,
                shift=Shift.FIRST,
                sheet="sheet1",
                instructor_available_slots=15,  # More available
                subject_prac_lab_hours=10,
            ),
            LectureStream(
                id="s2",
                subject="S2",
                instructor="I2",
                language="каз",
                groups=["G3", "G4"],
                student_count=50,
                hours_odd_week=1,
                hours_even_week=1,
                shift=Shift.FIRST,
                sheet="sheet1",
                instructor_available_slots=5,  # Less available → higher priority
                subject_prac_lab_hours=5,
            ),
        ]

        result = sort_streams_by_priority(streams)

        # s2 should come first (fewer available slots)
        assert result[0].id == "s2"
        assert result[1].id == "s1"

    def test_sorts_by_prac_lab_hours_second(self):
        from form1_parser.scheduler.models import LectureStream

        streams = [
            LectureStream(
                id="s1",
                subject="S1",
                instructor="I1",
                language="каз",
                groups=["G1", "G2"],
                student_count=100,
                hours_odd_week=1,
                hours_even_week=1,
                shift=Shift.FIRST,
                sheet="sheet1",
                instructor_available_slots=10,  # Same
                subject_prac_lab_hours=5,  # Less hours
            ),
            LectureStream(
                id="s2",
                subject="S2",
                instructor="I2",
                language="каз",
                groups=["G3", "G4"],
                student_count=50,
                hours_odd_week=1,
                hours_even_week=1,
                shift=Shift.FIRST,
                sheet="sheet1",
                instructor_available_slots=10,  # Same
                subject_prac_lab_hours=20,  # More hours → higher priority
            ),
        ]

        result = sort_streams_by_priority(streams)

        # s2 should come first (more prac/lab hours)
        assert result[0].id == "s2"
        assert result[1].id == "s1"

    def test_sorts_by_student_count_third(self):
        from form1_parser.scheduler.models import LectureStream

        streams = [
            LectureStream(
                id="s1",
                subject="S1",
                instructor="I1",
                language="каз",
                groups=["G1", "G2"],
                student_count=50,  # Less students
                hours_odd_week=1,
                hours_even_week=1,
                shift=Shift.FIRST,
                sheet="sheet1",
                instructor_available_slots=10,  # Same
                subject_prac_lab_hours=10,  # Same
            ),
            LectureStream(
                id="s2",
                subject="S2",
                instructor="I2",
                language="каз",
                groups=["G3", "G4"],
                student_count=100,  # More students → higher priority
                hours_odd_week=1,
                hours_even_week=1,
                shift=Shift.FIRST,
                sheet="sheet1",
                instructor_available_slots=10,  # Same
                subject_prac_lab_hours=10,  # Same
            ),
        ]

        result = sort_streams_by_priority(streams)

        # s2 should come first (more students)
        assert result[0].id == "s2"
        assert result[1].id == "s1"

    def test_three_tier_sorting_combined(self):
        from form1_parser.scheduler.models import LectureStream

        streams = [
            LectureStream(
                id="s1",
                subject="S1",
                instructor="I1",
                language="каз",
                groups=["G1", "G2"],
                student_count=100,
                hours_odd_week=1,
                hours_even_week=1,
                shift=Shift.FIRST,
                sheet="sheet1",
                instructor_available_slots=15,  # Most available → lowest priority
                subject_prac_lab_hours=10,
            ),
            LectureStream(
                id="s2",
                subject="S2",
                instructor="I2",
                language="каз",
                groups=["G3", "G4"],
                student_count=50,
                hours_odd_week=1,
                hours_even_week=1,
                shift=Shift.FIRST,
                sheet="sheet1",
                instructor_available_slots=5,  # Fewest available → highest priority
                subject_prac_lab_hours=5,
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
                instructor_available_slots=10,  # Middle
                subject_prac_lab_hours=15,  # Most prac/lab for this availability level
            ),
        ]

        result = sort_streams_by_priority(streams)

        # Order: s2 (5 slots), s3 (10 slots), s1 (15 slots)
        assert result[0].id == "s2"
        assert result[1].id == "s3"
        assert result[2].id == "s1"
