"""Pattern detection for Form-1 parser.

Detects which data entry pattern a subject uses:
- "1a": Horizontal - Individual (each row has its own Prac/Lab hours)
- "1b": Horizontal - Merged (NaN rows merge into previous stream)
- "implicit_subgroup": Same group repeated for subgroups
- "explicit_subgroup": Groups with explicit subgroup notation
"""

import pandas as pd

from .constants import (
    EXPLICIT_SUBGROUP_PATTERN,
    PATTERN_1A,
    PATTERN_1B,
    PATTERN_EXPLICIT_SUBGROUP,
    PATTERN_IMPLICIT_SUBGROUP,
)


def has_explicit_subgroups(groups: pd.Series) -> bool:
    """Check if any group has explicit subgroup notation.

    Looks for patterns: /1/, /2/, \\1\\, \\2\\, -1, -2

    Args:
        groups: Series of group names

    Returns:
        True if any group has explicit subgroup notation
    """
    return groups.str.contains(EXPLICIT_SUBGROUP_PATTERN, regex=True, na=False).any()


def has_implicit_subgroups(groups: pd.Series) -> bool:
    """Check if same group appears multiple times (implicit subgroups).

    Args:
        groups: Series of group names

    Returns:
        True if any group appears more than once
    """
    group_counts = groups.value_counts()
    return group_counts.max() > 1 if not group_counts.empty else False


def calculate_fill_rate(values: pd.Series) -> float:
    """Calculate the fill rate of a series (ratio of non-null values).

    Args:
        values: Series to check

    Returns:
        Fill rate between 0 and 1
    """
    if len(values) == 0:
        return 0.0

    # Count values that are not null and > 0
    filled = values.apply(lambda x: pd.notna(x) and float(x) > 0 if pd.notna(x) else False)
    return filled.mean()


def detect_pattern(subject_data: pd.DataFrame, group_col: str, practical_col: str) -> str:
    """Detect which data entry pattern a subject uses.

    Algorithm:
    1. Has explicit subgroup notation? → "explicit_subgroup"
    2. Same group appears multiple times? → "implicit_subgroup"
    3. Practical fill rate > 0.5? → "1a" (individual)
    4. Otherwise → "1b" (merged)

    Args:
        subject_data: DataFrame containing rows for a single subject
        group_col: Name of the group column
        practical_col: Name of the practical hours column

    Returns:
        Pattern name: "1a", "1b", "implicit_subgroup", or "explicit_subgroup"
    """
    groups = subject_data[group_col].dropna()

    if groups.empty:
        return PATTERN_1A  # Default to simplest pattern

    # Check for explicit subgroups first
    if has_explicit_subgroups(groups):
        return PATTERN_EXPLICIT_SUBGROUP

    # Check for implicit subgroups (same group repeated)
    if has_implicit_subgroups(groups):
        return PATTERN_IMPLICIT_SUBGROUP

    # Check practical fill rate for 1a vs 1b
    practical_values = subject_data[practical_col]
    fill_rate = calculate_fill_rate(practical_values)

    if fill_rate > 0.5:
        return PATTERN_1A  # Most rows have practical hours
    else:
        return PATTERN_1B  # Merged practicals


class PatternDetector:
    """Detects data entry patterns in Form-1 spreadsheets."""

    def __init__(self, group_col: str = "group", practical_col: str = "practical"):
        """Initialize detector.

        Args:
            group_col: Name of the group column
            practical_col: Name of the practical hours column
        """
        self.group_col = group_col
        self.practical_col = practical_col

    def detect(self, subject_data: pd.DataFrame) -> str:
        """Detect pattern for a subject's data.

        Args:
            subject_data: DataFrame containing rows for a single subject

        Returns:
            Pattern name
        """
        return detect_pattern(subject_data, self.group_col, self.practical_col)

    def get_pattern_info(self, pattern: str) -> dict:
        """Get information about a pattern.

        Args:
            pattern: Pattern name

        Returns:
            Dictionary with pattern description
        """
        info = {
            PATTERN_1A: {
                "name": "Horizontal - Individual",
                "description": "Each row has its own Practical/Lab hours",
                "lecture_rule": "Unique instructors with Lec > 0",
                "practical_rule": "Each row with Prac > 0 = 1 stream",
                "lab_rule": "Each row with Lab > 0 = 1 stream",
            },
            PATTERN_1B: {
                "name": "Horizontal - Merged",
                "description": "NaN in Prac/Lab means merged with previous stream",
                "lecture_rule": "Unique instructors with Lec > 0",
                "practical_rule": "Row with hours starts new stream; NaN rows merge into it",
                "lab_rule": "Same as practical",
            },
            PATTERN_IMPLICIT_SUBGROUP: {
                "name": "Implicit Subgroups",
                "description": "Same group repeated for subgroups (typically labs)",
                "lecture_rule": "Unique instructors with Lec > 0",
                "practical_rule": "FIRST occurrence per group with Prac > 0",
                "lab_rule": "EVERY row with Lab > 0 (each is separate stream)",
            },
            PATTERN_EXPLICIT_SUBGROUP: {
                "name": "Explicit Subgroups",
                "description": "Groups with explicit subgroup notation (/1/, \\1\\, -1)",
                "lecture_rule": "Unique instructors with Lec > 0",
                "practical_rule": "Each subgroup row with Prac > 0 = 1 stream",
                "lab_rule": "Each subgroup row with Lab > 0 = 1 stream",
            },
        }

        return info.get(pattern, {"name": "Unknown", "description": "Unknown pattern"})
