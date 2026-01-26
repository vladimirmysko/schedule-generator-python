"""Tests for utility functions."""

import pandas as pd
import pytest

from form1_parser.exceptions import InvalidHoursError
from form1_parser.utils import (
    calculate_weekly_hours,
    clean_instructor_name,
    extract_base_group,
    forward_fill_student_counts,
    has_explicit_subgroup,
    normalize_group_name,
    safe_int,
    safe_str,
)


class TestCalculateWeeklyHours:
    """Tests for calculate_weekly_hours function."""

    def test_7_hours(self):
        """Test 7 total hours (0 odd, 1 even)."""
        odd, even = calculate_weekly_hours(7)
        assert odd == 0
        assert even == 1

    def test_8_hours(self):
        """Test 8 total hours (1 odd, 0 even)."""
        odd, even = calculate_weekly_hours(8)
        assert odd == 1
        assert even == 0

    def test_15_hours(self):
        """Test 15 total hours (1 odd, 1 even)."""
        odd, even = calculate_weekly_hours(15)
        assert odd == 1
        assert even == 1

    def test_30_hours(self):
        """Test 30 total hours (2 odd, 2 even)."""
        odd, even = calculate_weekly_hours(30)
        assert odd == 2
        assert even == 2

    def test_invalid_hours(self):
        """Test invalid hours raises error."""
        with pytest.raises(InvalidHoursError):
            calculate_weekly_hours(10)


class TestNormalizeGroupName:
    """Tests for normalize_group_name function."""

    def test_regular_group(self):
        """Test normalizing a regular group name."""
        assert normalize_group_name("СТР-21 О") == "СТР-21 О"

    def test_group_with_forward_slash_subgroup(self):
        """Test removing forward slash subgroup notation."""
        assert normalize_group_name("АРХ-11 О /1/") == "АРХ-11 О"
        assert normalize_group_name("АРХ-11 О /2/") == "АРХ-11 О"

    def test_group_with_backslash_subgroup(self):
        """Test removing backslash subgroup notation."""
        assert normalize_group_name("АРХ-11 О \\1\\") == "АРХ-11 О"

    def test_group_with_dash_subgroup(self):
        """Test removing dash subgroup notation."""
        assert normalize_group_name("АРХ-15 О -1") == "АРХ-15 О"
        assert normalize_group_name("АРХ-15 О -2") == "АРХ-15 О"

    def test_empty_group(self):
        """Test empty group name."""
        assert normalize_group_name("") == ""
        assert normalize_group_name(None) == ""

    def test_nan_group(self):
        """Test NaN group name."""
        assert normalize_group_name(pd.NA) == ""


class TestHasExplicitSubgroup:
    """Tests for has_explicit_subgroup function."""

    def test_forward_slash_notation(self):
        """Test detection of forward slash notation."""
        assert has_explicit_subgroup("АРХ-11 О /1/") is True
        assert has_explicit_subgroup("АРХ-11 О /2/") is True

    def test_backslash_notation(self):
        """Test detection of backslash notation."""
        assert has_explicit_subgroup("АРХ-11 О \\1\\") is True
        assert has_explicit_subgroup("АРХ-11 О \\2\\") is True

    def test_dash_notation(self):
        """Test detection of dash notation."""
        assert has_explicit_subgroup("АРХ-15 О -1") is True
        assert has_explicit_subgroup("АРХ-15 О -2") is True

    def test_no_subgroup(self):
        """Test groups without subgroup notation."""
        assert has_explicit_subgroup("СТР-21 О") is False
        assert has_explicit_subgroup("ВЕТ-32 О") is False

    def test_study_form_notation(self):
        """Test study form notation is not confused with subgroups."""
        # /у/ and /г/ are study forms, not subgroups
        assert has_explicit_subgroup("АРХ-11 О /у/") is False
        assert has_explicit_subgroup("АРХ-11 О /г/") is False

    def test_empty_values(self):
        """Test empty values."""
        assert has_explicit_subgroup("") is False
        assert has_explicit_subgroup(None) is False


class TestExtractBaseGroup:
    """Tests for extract_base_group function."""

    def test_base_group_extraction(self):
        """Test extracting base group name."""
        assert extract_base_group("АРХ-11 О /1/") == "АРХ-11 О"
        assert extract_base_group("СТР-21 О") == "СТР-21 О"


class TestSafeInt:
    """Tests for safe_int function."""

    def test_integer_value(self):
        """Test with integer input."""
        assert safe_int(42) == 42

    def test_float_value(self):
        """Test with float input."""
        assert safe_int(42.7) == 42

    def test_string_value(self):
        """Test with string input."""
        assert safe_int("42") == 42

    def test_nan_value(self):
        """Test with NaN input."""
        assert safe_int(pd.NA) == 0
        assert safe_int(float("nan")) == 0

    def test_invalid_value(self):
        """Test with invalid input."""
        assert safe_int("abc") == 0
        assert safe_int(None, default=0) == 0

    def test_custom_default(self):
        """Test with custom default value."""
        assert safe_int(None, default=-1) == -1


class TestSafeStr:
    """Tests for safe_str function."""

    def test_string_value(self):
        """Test with string input."""
        assert safe_str("hello") == "hello"

    def test_integer_value(self):
        """Test with integer input."""
        assert safe_str(42) == "42"

    def test_nan_value(self):
        """Test with NaN input."""
        assert safe_str(pd.NA) == ""

    def test_whitespace_trimming(self):
        """Test whitespace is trimmed."""
        assert safe_str("  hello  ") == "hello"


class TestCleanInstructorName:
    """Tests for clean_instructor_name function."""

    def test_normal_name(self):
        """Test cleaning a normal name."""
        assert clean_instructor_name("Иванов А.О.") == "Иванов А.О."

    def test_extra_whitespace(self):
        """Test removing extra whitespace."""
        assert clean_instructor_name("Иванов   А.О.") == "Иванов А.О."
        assert clean_instructor_name("  Иванов А.О.  ") == "Иванов А.О."

    def test_empty_value(self):
        """Test empty values."""
        assert clean_instructor_name("") == ""
        assert clean_instructor_name(None) == ""


class TestForwardFillStudentCounts:
    """Tests for forward_fill_student_counts function."""

    def test_fills_nan_from_previous_same_group(self):
        """Test that NaN student count is filled from previous row with same group."""
        df = pd.DataFrame(
            {
                "subject": ["Math", "Math"],
                "group": ["ВТИС-31 О", "ВТИС-31 О"],
                "students": [24, pd.NA],
            }
        )
        result = forward_fill_student_counts(df)
        assert result.at[1, "students"] == 24

    def test_fills_zero_from_previous_same_group(self):
        """Test that 0 student count is filled from previous row with same group."""
        df = pd.DataFrame(
            {
                "subject": ["Math", "Math"],
                "group": ["ВТИС-31 О", "ВТИС-31 О"],
                "students": [24, 0],
            }
        )
        result = forward_fill_student_counts(df)
        assert result.at[1, "students"] == 24

    def test_does_not_fill_across_subjects(self):
        """Test that student count is not inherited across different subjects."""
        df = pd.DataFrame(
            {
                "subject": ["Math", "Physics"],
                "group": ["ВТИС-31 О", "ВТИС-31 О"],
                "students": [24, pd.NA],
            }
        )
        result = forward_fill_student_counts(df)
        assert pd.isna(result.at[1, "students"])

    def test_subgroups_divide_student_count(self):
        """Test that explicit subgroups get divided student count."""
        df = pd.DataFrame(
            {
                "subject": ["Math", "Math", "Math"],
                "group": ["ВТИС-31 О", "ВТИС-31 О /1/", "ВТИС-31 О /2/"],
                "students": [24, pd.NA, pd.NA],
            }
        )
        result = forward_fill_student_counts(df)
        # 24 students / 2 subgroups = 12 each
        assert result.at[1, "students"] == 12
        assert result.at[2, "students"] == 12

    def test_subgroups_no_base_row_uses_first_subgroup_count(self):
        """Test that subgroups without base row use first subgroup's count."""
        df = pd.DataFrame(
            {
                "subject": ["Math", "Math"],
                "group": ["ВТИС-31 О /1/", "ВТИС-31 О /2/"],
                "students": [24, pd.NA],
            }
        )
        result = forward_fill_student_counts(df)
        # 24 students from /1/ / 2 subgroups = 12 each
        assert result.at[0, "students"] == 12
        assert result.at[1, "students"] == 12

    def test_subgroups_no_counts_at_all_stays_empty(self):
        """Test that subgroups without any count stay empty."""
        df = pd.DataFrame(
            {
                "subject": ["Math", "Math"],
                "group": ["ВТИС-31 О /1/", "ВТИС-31 О /2/"],
                "students": [pd.NA, pd.NA],
            }
        )
        result = forward_fill_student_counts(df)
        assert pd.isna(result.at[0, "students"])
        assert pd.isna(result.at[1, "students"])

    def test_different_groups_tracked_separately(self):
        """Test that different groups maintain separate student counts."""
        df = pd.DataFrame(
            {
                "subject": ["Math", "Math", "Math", "Math"],
                "group": ["ВТИС-31 О", "ВТИС-32 О", "ВТИС-31 О", "ВТИС-32 О"],
                "students": [24, 21, pd.NA, pd.NA],
            }
        )
        result = forward_fill_student_counts(df)
        assert result.at[2, "students"] == 24
        assert result.at[3, "students"] == 21

    def test_multiple_subjects_same_group(self):
        """Test correct filling when same group appears in multiple subjects."""
        df = pd.DataFrame(
            {
                "subject": ["Math", "Math", "Physics", "Physics"],
                "group": ["ВТИС-31 О", "ВТИС-31 О", "ВТИС-31 О", "ВТИС-31 О"],
                "students": [24, pd.NA, 20, pd.NA],
            }
        )
        result = forward_fill_student_counts(df)
        assert result.at[1, "students"] == 24
        assert result.at[3, "students"] == 20

    def test_empty_group_skipped(self):
        """Test that rows with empty group are skipped."""
        df = pd.DataFrame(
            {
                "subject": ["Math", "Math"],
                "group": ["ВТИС-31 О", ""],
                "students": [24, pd.NA],
            }
        )
        result = forward_fill_student_counts(df)
        assert pd.isna(result.at[1, "students"])
