"""Validation logic for Form-1 parser."""

import re

import pandas as pd

from .constants import GROUP_NAME_PATTERN, VALID_LANGUAGES


def validate_group_name(group_name: str) -> tuple[bool, str | None]:
    """Validate a group name.

    Expected format: Cyrillic letters + hyphen + 2 digits + optional letter + optional 'О'
    Example: СТР-21 О, АРХ-11, ВЕТ-32 О

    Args:
        group_name: Group name to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not group_name or pd.isna(group_name):
        return False, "Group name is empty"

    name = str(group_name).strip()

    if len(name) < 3:
        return False, f"Group name too short: '{name}'"

    if not re.match(GROUP_NAME_PATTERN, name):
        return False, f"Group name doesn't match expected pattern: '{name}'"

    return True, None


def validate_language(language: str) -> tuple[bool, str | None]:
    """Validate language value.

    Args:
        language: Language value (should be 'каз' or 'орыс')

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not language or pd.isna(language):
        return False, "Language is empty"

    lang = str(language).strip().lower()

    if lang not in VALID_LANGUAGES:
        return False, f"Invalid language: '{language}'. Expected: {', '.join(VALID_LANGUAGES)}"

    return True, None


def validate_hours(hours: int, field_name: str = "hours") -> tuple[bool, str | None]:
    """Validate hours value.

    Args:
        hours: Hours value to validate
        field_name: Name of the field for error message

    Returns:
        Tuple of (is_valid, error_message)
    """
    if pd.isna(hours):
        return True, None  # NaN is valid (means no hours for this type)

    try:
        h = int(float(hours))
    except (ValueError, TypeError):
        return False, f"Invalid {field_name} value: '{hours}'"

    if h < 0:
        return False, f"Negative {field_name}: {h}"

    if h > 100:
        return False, f"Unusually high {field_name}: {h}"

    return True, None


def validate_student_count(count: int) -> tuple[bool, str | None]:
    """Validate student count.

    Args:
        count: Student count to validate

    Returns:
        Tuple of (is_valid, warning_message)
    """
    if pd.isna(count) or count == 0:
        return True, "Student count is 0 or missing"

    try:
        c = int(float(count))
    except (ValueError, TypeError):
        return False, f"Invalid student count: '{count}'"

    if c < 0:
        return False, f"Negative student count: {c}"

    if c > 500:
        return True, f"Unusually high student count: {c}"

    return True, None


def validate_subject_name(subject: str) -> tuple[bool, str | None]:
    """Validate subject name.

    Args:
        subject: Subject name to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not subject or pd.isna(subject):
        return False, "Subject name is empty"

    name = str(subject).strip()

    if len(name) < 2:
        return False, f"Subject name too short: '{name}'"

    return True, None


def validate_instructor(instructor: str) -> tuple[bool, str | None]:
    """Validate instructor name.

    Args:
        instructor: Instructor name to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not instructor or pd.isna(instructor):
        return False, "Instructor name is empty"

    name = str(instructor).strip()

    if len(name) < 2:
        return False, f"Instructor name too short: '{name}'"

    return True, None


def validate_row_has_hours(lecture: int, practical: int, lab: int) -> tuple[bool, str | None]:
    """Validate that at least one hours field is positive.

    Args:
        lecture: Lecture hours
        practical: Practical hours
        lab: Lab hours

    Returns:
        Tuple of (is_valid, error_message)
    """
    lec = 0 if pd.isna(lecture) else int(float(lecture)) if lecture else 0
    prac = 0 if pd.isna(practical) else int(float(practical)) if practical else 0
    labs = 0 if pd.isna(lab) else int(float(lab)) if lab else 0

    if lec <= 0 and prac <= 0 and labs <= 0:
        return False, "Row has no hours (all lecture/practical/lab values are 0 or empty)"

    return True, None


class RowValidator:
    """Validates a single data row from the spreadsheet."""

    def __init__(self, row: pd.Series, row_index: int, sheet_name: str):
        self.row = row
        self.row_index = row_index
        self.sheet_name = sheet_name
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def validate_all(
        self,
        subject: str,
        group: str,
        language: str,
        student_count: int,
        lecture: int,
        practical: int,
        lab: int,
        instructor: str,
    ) -> tuple[bool, list[str], list[str]]:
        """Run all validations on row data.

        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        self.errors = []
        self.warnings = []

        # Required field validations
        valid, msg = validate_subject_name(subject)
        if not valid:
            self.errors.append(f"Row {self.row_index}: {msg}")

        valid, msg = validate_group_name(group)
        if not valid:
            self.errors.append(f"Row {self.row_index}: {msg}")

        valid, msg = validate_language(language)
        if not valid:
            self.errors.append(f"Row {self.row_index}: {msg}")

        # Hours validation
        for hours, name in [(lecture, "lecture"), (practical, "practical"), (lab, "lab")]:
            valid, msg = validate_hours(hours, name)
            if not valid:
                self.errors.append(f"Row {self.row_index}: {msg}")

        # Instructor validation (only if row has hours)
        valid, _ = validate_row_has_hours(lecture, practical, lab)
        if valid:
            valid, msg = validate_instructor(instructor)
            if not valid:
                self.errors.append(f"Row {self.row_index}: {msg}")

        # Warnings
        valid, msg = validate_student_count(student_count)
        if msg:
            self.warnings.append(f"Row {self.row_index}: {msg}")

        return len(self.errors) == 0, self.errors, self.warnings
