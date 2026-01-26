"""Utility functions for Form-1 parser."""

import re
import uuid

import pandas as pd

from .constants import (
    COL_NUMBER,
    COL_SUBJECT,
    DATA_START_MARKERS,
    EXPLICIT_SUBGROUP_PATTERN,
    INSTRUCTOR_MARKERS,
    KNOWN_INSTRUCTOR_COLUMNS,
)
from .exceptions import DataStartNotFoundError, InstructorColumnNotFoundError
from .models import WeeklyHours
from .normalization import normalize_instructor_name


def calculate_weekly_hours(total_hours: int) -> tuple[int, int]:
    """Calculate hours per odd and even week from total semester hours.

    Formula: total = odd_week × 8 + even_week × 7

    Args:
        total_hours: Total semester hours from spreadsheet

    Returns:
        Tuple of (odd_week_hours, even_week_hours)

    Raises:
        ValueError: If total_hours doesn't fit the formula
    """
    weekly = WeeklyHours.from_total(total_hours)
    return (weekly.odd_week, weekly.even_week)


def find_data_start_row(df: pd.DataFrame, sheet_name: str) -> int:
    """Find the row where actual data starts.

    Looks for marker '1', '2 семестр', or '2семестр' in column 0.

    Args:
        df: DataFrame of the sheet
        sheet_name: Name of the sheet (for error message)

    Returns:
        Index of the data start row

    Raises:
        DataStartNotFoundError: If data start cannot be found
    """
    for idx, row in df.iterrows():
        val = (
            str(row.iloc[COL_NUMBER]).strip() if pd.notna(row.iloc[COL_NUMBER]) else ""
        )
        if val in DATA_START_MARKERS:
            # If it's a semester marker, skip to next row
            if "семестр" in val.lower():
                return idx + 1
            return idx

    raise DataStartNotFoundError(sheet_name)


def find_instructor_column(df: pd.DataFrame, sheet_name: str) -> int:
    """Find the rightmost column containing instructor names.

    Searches from right to left for columns containing instructor markers
    (проф, а.о., с.п., асс, доц).

    Args:
        df: DataFrame of the sheet
        sheet_name: Name of the sheet

    Returns:
        Column index of the instructor column

    Raises:
        InstructorColumnNotFoundError: If instructor column cannot be found
    """
    # First try known column positions
    if sheet_name in KNOWN_INSTRUCTOR_COLUMNS:
        known_col = KNOWN_INSTRUCTOR_COLUMNS[sheet_name]
        if known_col < len(df.columns):
            return known_col

    # Search from right to left
    for col in range(len(df.columns) - 1, -1, -1):
        for row in range(11, min(50, len(df))):
            if row >= len(df):
                break
            val = str(df.iloc[row, col]).lower() if pd.notna(df.iloc[row, col]) else ""
            if any(marker in val for marker in INSTRUCTOR_MARKERS):
                return col

    raise InstructorColumnNotFoundError(sheet_name)


def forward_fill_subject_names(df: pd.DataFrame) -> pd.DataFrame:
    """Forward-fill subject names in the DataFrame.

    Subject names appear only in the first row of each subject block.
    This function propagates subject names to subsequent rows.

    Args:
        df: DataFrame with subject column

    Returns:
        DataFrame with forward-filled subject names
    """
    df = df.copy()
    # Forward fill the subject column
    df.iloc[:, COL_SUBJECT] = df.iloc[:, COL_SUBJECT].ffill()
    return df


def forward_fill_student_counts(
    df: pd.DataFrame,
    group_col: str = "group",
    students_col: str = "students",
    subject_col: str = "subject",
) -> pd.DataFrame:
    """Forward-fill student counts within same normalized group and subject.

    For regular rows (no subgroup notation):
    - Inherit student count from previous row with same subject and normalized group

    For explicit subgroups (/1/, /2/, etc.):
    - Divide base group's student count by number of subgroups
    - If no base group exists, use the first subgroup's count as the total

    Args:
        df: DataFrame with group, students, and subject columns
        group_col: Name of the group column
        students_col: Name of the students column
        subject_col: Name of the subject column

    Returns:
        DataFrame with forward-filled student counts
    """
    df = df.copy()

    # First pass: collect base counts and count subgroups per (subject, base_group)
    base_counts: dict[tuple[str, str], int] = {}
    subgroup_counts: dict[tuple[str, str], set[str]] = {}
    subgroup_first_count: dict[tuple[str, str], int] = {}

    for idx in df.index:
        subject = safe_str(df.at[idx, subject_col])
        group = safe_str(df.at[idx, group_col])
        students = df.at[idx, students_col]

        if not group:
            continue

        normalized = normalize_group_name(group)
        key = (subject, normalized)

        if has_explicit_subgroup(group):
            # Track unique subgroup names
            if key not in subgroup_counts:
                subgroup_counts[key] = set()
            subgroup_counts[key].add(group)
            # Track first subgroup's count (fallback when no base row exists)
            if (
                key not in subgroup_first_count
                and not pd.isna(students)
                and students != 0
            ):
                subgroup_first_count[key] = safe_int(students)
        else:
            # Track base group student count
            if not pd.isna(students) and students != 0:
                base_counts[key] = safe_int(students)

    # Second pass: fill in values
    last_counts: dict[tuple[str, str], int] = {}

    for idx in df.index:
        subject = safe_str(df.at[idx, subject_col])
        group = safe_str(df.at[idx, group_col])
        students = df.at[idx, students_col]

        if not group:
            continue

        normalized = normalize_group_name(group)
        key = (subject, normalized)

        if has_explicit_subgroup(group):
            # For subgroups: divide total count by number of subgroups
            if key in subgroup_counts:
                num_subgroups = len(subgroup_counts[key])
                # Use base count if available, otherwise use first subgroup's count
                total_count = base_counts.get(key) or subgroup_first_count.get(key)
                if total_count:
                    df.at[idx, students_col] = total_count // num_subgroups
        else:
            # For regular groups: forward-fill from previous same group
            if pd.isna(students) or students == 0:
                if key in last_counts:
                    df.at[idx, students_col] = last_counts[key]
            else:
                last_counts[key] = safe_int(students)

    return df


def normalize_group_name(group_name: str) -> str:
    """Normalize a group name by removing subgroup notation.

    Strips explicit subgroup markers (/1/, \\1\\, -1) but preserves
    study form markers (/у/, /г/).

    Args:
        group_name: Raw group name from spreadsheet

    Returns:
        Normalized group name
    """
    # Check for NA/None first to avoid boolean ambiguity
    try:
        if pd.isna(group_name):
            return ""
    except (ValueError, TypeError):
        pass

    if not group_name:
        return ""

    name = str(group_name).strip()

    # Remove explicit subgroup notation
    name = re.sub(EXPLICIT_SUBGROUP_PATTERN, "", name)

    return name.strip()


def extract_base_group(group_name: str) -> str:
    """Extract base group name without any modifiers.

    Args:
        group_name: Group name potentially with subgroup notation

    Returns:
        Base group name
    """
    return normalize_group_name(group_name)


def has_explicit_subgroup(group_name: str) -> bool:
    """Check if group name has explicit subgroup notation.

    Args:
        group_name: Group name to check

    Returns:
        True if contains /1/, /2/, \\1\\, \\2\\, -1, or -2
    """
    if not group_name or pd.isna(group_name):
        return False

    return bool(re.search(EXPLICIT_SUBGROUP_PATTERN, str(group_name)))


def generate_stream_id(
    subject: str, stream_type: str, instructor: str, index: int
) -> str:
    """Generate a unique stream ID.

    Args:
        subject: Subject name
        stream_type: Type of stream (lecture/practical/lab)
        instructor: Instructor name
        index: Index for uniqueness

    Returns:
        Unique stream ID
    """
    # Create a short hash based on components
    base = f"{subject[:10]}_{stream_type[:3]}_{instructor[:10]}_{index}"
    unique_part = uuid.uuid4().hex[:8]
    return f"{base}_{unique_part}".replace(" ", "_")


def safe_int(value, default: int = 0) -> int:
    """Safely convert a value to integer.

    Args:
        value: Value to convert
        default: Default value if conversion fails

    Returns:
        Integer value
    """
    if pd.isna(value):
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def safe_str(value, default: str = "") -> str:
    """Safely convert a value to string.

    Args:
        value: Value to convert
        default: Default value if conversion fails

    Returns:
        String value
    """
    if pd.isna(value):
        return default
    return str(value).strip()


def clean_instructor_name(name: str) -> str:
    """Clean and normalize instructor name.

    Args:
        name: Raw instructor name

    Returns:
        Cleaned instructor name with prefixes removed
    """
    return normalize_instructor_name(name)
