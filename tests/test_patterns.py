"""Tests for pattern detection."""

import pandas as pd
import pytest

from form1_parser.constants import (
    PATTERN_1A,
    PATTERN_1B,
    PATTERN_EXPLICIT_SUBGROUP,
    PATTERN_IMPLICIT_SUBGROUP,
)
from form1_parser.patterns import (
    PatternDetector,
    calculate_fill_rate,
    detect_pattern,
    has_explicit_subgroups,
    has_implicit_subgroups,
)


class TestHasExplicitSubgroups:
    """Tests for has_explicit_subgroups function."""

    def test_with_forward_slash_subgroups(self):
        """Test detection of forward slash notation."""
        groups = pd.Series(["АРХ-11 О /1/", "АРХ-11 О /2/", "СТР-21 О"])
        assert has_explicit_subgroups(groups) == True

    def test_with_backslash_subgroups(self):
        """Test detection of backslash notation."""
        groups = pd.Series(["АРХ-11 О \\1\\", "АРХ-11 О \\2\\"])
        assert has_explicit_subgroups(groups) == True

    def test_with_dash_subgroups(self):
        """Test detection of dash notation."""
        groups = pd.Series(["АРХ-15 О -1", "АРХ-15 О -2"])
        assert has_explicit_subgroups(groups) == True

    def test_without_subgroups(self):
        """Test regular groups without subgroup notation."""
        groups = pd.Series(["СТР-21 О", "СТР-22 О", "СТР-23 О"])
        assert has_explicit_subgroups(groups) == False

    def test_empty_series(self):
        """Test empty series."""
        groups = pd.Series([], dtype=str)
        assert has_explicit_subgroups(groups) == False


class TestHasImplicitSubgroups:
    """Tests for has_implicit_subgroups function."""

    def test_with_repeated_groups(self):
        """Test detection of repeated groups."""
        groups = pd.Series(["СТР-21 О", "СТР-21 О", "СТР-22 О"])
        assert has_implicit_subgroups(groups) == True

    def test_without_repeated_groups(self):
        """Test unique groups."""
        groups = pd.Series(["СТР-21 О", "СТР-22 О", "СТР-23 О"])
        assert has_implicit_subgroups(groups) == False

    def test_empty_series(self):
        """Test empty series."""
        groups = pd.Series([], dtype=str)
        assert has_implicit_subgroups(groups) == False


class TestCalculateFillRate:
    """Tests for calculate_fill_rate function."""

    def test_full_fill(self):
        """Test all values filled."""
        values = pd.Series([10, 20, 30])
        assert calculate_fill_rate(values) == 1.0

    def test_no_fill(self):
        """Test no values filled."""
        values = pd.Series([0, 0, 0])
        assert calculate_fill_rate(values) == 0.0

    def test_partial_fill(self):
        """Test partial fill."""
        values = pd.Series([10, 0, 30, 0])
        assert calculate_fill_rate(values) == 0.5

    def test_with_nan(self):
        """Test with NaN values."""
        values = pd.Series([10, float("nan"), 30, float("nan")])
        assert calculate_fill_rate(values) == 0.5

    def test_empty_series(self):
        """Test empty series."""
        values = pd.Series([], dtype=float)
        assert calculate_fill_rate(values) == 0.0


class TestDetectPattern:
    """Tests for detect_pattern function."""

    def test_pattern_1a_detection(self, sample_pattern_1a_data):
        """Test Pattern 1a detection (high fill rate)."""
        pattern = detect_pattern(sample_pattern_1a_data, "group", "practical")
        assert pattern == PATTERN_1A

    def test_pattern_1b_detection(self, sample_pattern_1b_data):
        """Test Pattern 1b detection (low fill rate)."""
        pattern = detect_pattern(sample_pattern_1b_data, "group", "practical")
        assert pattern == PATTERN_1B

    def test_implicit_subgroup_detection(self, sample_implicit_subgroup_data):
        """Test implicit subgroup detection (repeated groups)."""
        pattern = detect_pattern(sample_implicit_subgroup_data, "group", "practical")
        assert pattern == PATTERN_IMPLICIT_SUBGROUP

    def test_explicit_subgroup_detection(self, sample_explicit_subgroup_data):
        """Test explicit subgroup detection (subgroup notation)."""
        pattern = detect_pattern(sample_explicit_subgroup_data, "group", "practical")
        assert pattern == PATTERN_EXPLICIT_SUBGROUP

    def test_empty_dataframe(self):
        """Test with empty DataFrame."""
        df = pd.DataFrame({"group": [], "practical": []})
        pattern = detect_pattern(df, "group", "practical")
        assert pattern == PATTERN_1A  # Default pattern


class TestPatternDetector:
    """Tests for PatternDetector class."""

    def test_detector_initialization(self):
        """Test detector initialization."""
        detector = PatternDetector(group_col="group", practical_col="practical")
        assert detector.group_col == "group"
        assert detector.practical_col == "practical"

    def test_detect_method(self, sample_pattern_1a_data):
        """Test detect method."""
        detector = PatternDetector()
        pattern = detector.detect(sample_pattern_1a_data)
        assert pattern == PATTERN_1A

    def test_get_pattern_info_1a(self):
        """Test getting pattern info for 1a."""
        detector = PatternDetector()
        info = detector.get_pattern_info(PATTERN_1A)

        assert info["name"] == "Horizontal - Individual"
        assert "description" in info
        assert "lecture_rule" in info
        assert "practical_rule" in info
        assert "lab_rule" in info

    def test_get_pattern_info_unknown(self):
        """Test getting info for unknown pattern."""
        detector = PatternDetector()
        info = detector.get_pattern_info("unknown_pattern")

        assert info["name"] == "Unknown"
