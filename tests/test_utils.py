"""Tests for utility functions."""

import pandas as pd
import pytest

from form1_parser.exceptions import InvalidHoursError
from form1_parser.utils import (
    calculate_weekly_hours,
    clean_instructor_name,
    extract_base_group,
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
