"""Utility functions for schedule generation."""

import re

from .constants import STAGE1_MIN_GROUPS, YEAR_SHIFT_MAP, Shift
from .models import LectureStream


def parse_group_year(group_name: str) -> int:
    """Extract year from group name.

    Group names follow patterns like:
    - "АРХ-21 О" -> year 2 (21 means 2021 enrollment, so 2nd year in 2022-2023)
    - "СТР-15 О" -> year 1 (15 means 2015 enrollment pattern, actually means 1st year)
    - "ВТИС-21 О" -> year 2

    The year is determined by the last digit of the number:
    - 1, 11, 21, etc. = 1st year
    - 3, 13, 23, etc. = 2nd year
    - 5, 15, 25, etc. = 3rd year
    - 7, 17, 27, etc. = 4th year
    - 9, 19, 29, etc. = 5th year

    Note: The number in group names represents the enrollment year in a coded format
    where odd numbers indicate different years of study.

    Args:
        group_name: Group name like "АРХ-21 О"

    Returns:
        Year number (1-5), defaults to 1 if unable to parse
    """
    # Extract numbers from group name
    match = re.search(r"-(\d+)", group_name)
    if not match:
        return 1

    number = int(match.group(1))
    last_digit = number % 10

    # Map last digit to year
    if last_digit == 1:
        return 1
    elif last_digit == 3:
        return 2
    elif last_digit == 5:
        return 3
    elif last_digit == 7:
        return 4
    elif last_digit == 9:
        return 5
    else:
        # For numbers like 15, 25, etc., use the decade digit
        decade_digit = (number // 10) % 10
        if decade_digit % 2 == 1:  # Odd decade
            return min(5, (last_digit // 2) + 1)
        return 1


def parse_specialty_code(group_name: str) -> str:
    """Extract specialty code from group name.

    Args:
        group_name: Group name like "АРХ-21 О"

    Returns:
        Specialty code like "АРХ"
    """
    match = re.match(r"([А-ЯA-Z]+)", group_name)
    if match:
        return match.group(1)
    return ""


def determine_shift(groups: list[str]) -> Shift:
    """Determine shift based on group years.

    Rules:
    - 1st year: First shift (mandatory)
    - 2nd year: Second shift (mandatory)
    - 3rd year: First shift (default)
    - 4th/5th year: Second shift (default)

    For multiple groups, use the first group's year (all assumed same year).

    Args:
        groups: List of group names

    Returns:
        Shift enum value
    """
    if not groups:
        return Shift.FIRST

    # Use first group to determine year (all groups assumed same year)
    year = parse_group_year(groups[0])
    return YEAR_SHIFT_MAP.get(year, Shift.FIRST)


def clean_instructor_name(name: str) -> str:
    """Clean instructor name by removing prefixes.

    Args:
        name: Original instructor name like "а.о.Уахасов Қ.С."

    Returns:
        Cleaned name like "Уахасов Қ.С."
    """
    prefixes = [
        # Russian academic prefixes
        r"^а\.о\.\s*",           # а.о. (assistant)
        r"^а\.о\s+",             # а.о  (with space)
        r"^с\.п\.\.*\s*",        # с.п. and с.п.. (senior lecturer, handles typo)
        r"^с\.п\s+",             # с.п  (with space)
        r"^доцент\s*",           # доцент (associate professor - full)
        r"^д\.\s*",              # д. (abbreviated доцент)
        r"^асс\.проф\.\s*",      # асс.проф. (assistant professor)
        r"^қ\.проф\.\s*",        # қ.проф. (Kazakh: associate professor)
        r"^проф\.\s*",           # проф. (professor - abbreviated)
        r"^профессор\s*",        # профессор (professor - full)
        r"^ст\.преп\.\s*",       # ст.преп. (senior lecturer)
        r"^преподаватель\s*",    # преподаватель (lecturer - full)
        r"^п\.\s*",              # п. (abbreviated преподаватель)
        r"^о\.\s*",              # о. (unknown, found in data)
        # English prefixes
        r"^prof\.\s*",           # prof. (professor)
        r"^Dr\s+",               # Dr (doctor)
    ]
    cleaned = name.strip()
    for prefix in prefixes:
        cleaned = re.sub(prefix, "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def filter_stage1_lectures(streams: list[dict]) -> list[LectureStream]:
    """Filter and convert streams to LectureStream objects for Stage 1.

    Stage 1 criteria:
    - Type is "lecture"
    - Has at least STAGE1_MIN_GROUPS groups

    Args:
        streams: List of stream dictionaries from parsed JSON

    Returns:
        List of LectureStream objects ready for scheduling
    """
    lecture_streams = []

    for stream in streams:
        # Filter: only lectures with 2+ groups
        if stream.get("stream_type") != "lecture":
            continue

        groups = stream.get("groups", [])
        if len(groups) < STAGE1_MIN_GROUPS:
            continue

        hours = stream.get("hours", {})
        odd_week = hours.get("odd_week", 0)
        even_week = hours.get("even_week", 0)

        # Skip streams with no hours
        if odd_week == 0 and even_week == 0:
            continue

        # Determine shift from groups
        shift = determine_shift(groups)

        lecture_stream = LectureStream(
            id=stream.get("id", ""),
            subject=stream.get("subject", ""),
            instructor=stream.get("instructor", ""),
            language=stream.get("language", ""),
            groups=groups,
            student_count=stream.get("student_count", 0),
            hours_odd_week=odd_week,
            hours_even_week=even_week,
            shift=shift,
            sheet=stream.get("sheet", ""),
        )
        lecture_streams.append(lecture_stream)

    return lecture_streams


def sort_streams_by_priority(streams: list[LectureStream]) -> list[LectureStream]:
    """Sort streams by scheduling priority (largest student count first).

    Args:
        streams: List of LectureStream objects

    Returns:
        Sorted list with highest priority first
    """
    return sorted(streams, key=lambda s: -s.student_count)
