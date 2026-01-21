"""Utility functions for schedule generation."""

import re

from .constants import (
    FIRST_SHIFT_SLOTS,
    FLEXIBLE_SCHEDULE_SUBJECTS,
    SECOND_SHIFT_SLOTS,
    STAGE1_DAYS,
    STAGE1_MIN_GROUPS,
    TIME_SLOTS,
    YEAR_SHIFT_MAP,
    Shift,
)
from .models import LectureStream


def parse_group_year(group_name: str) -> int:
    """Extract year from group name.

    Group names follow patterns like:
    - "АРХ-11 О" -> year 1 (first digit 1 = 1st year)
    - "АРХ-21 О" -> year 2 (first digit 2 = 2nd year)
    - "АРХ-31 О" -> year 3 (first digit 3 = 3rd year)
    - "АРХ-41 О" -> year 4 (first digit 4 = 4th year)

    The year is determined by the first digit of the two-digit number:
    - 1x (11, 13, 15, 17, 19) = 1st year
    - 2x (21, 23, 25, 27, 29) = 2nd year
    - 3x (31, 33, 35, 37, 39) = 3rd year
    - 4x (41, 43, 45, 47, 49) = 4th year
    - 5x (51, 53, 55, 57, 59) = 5th year

    Note: The second digit typically indicates the group number within the year
    (odd numbers for Kazakh groups, even for Russian groups).

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

    # For two-digit numbers, the first digit indicates the year
    if 10 <= number <= 59:
        first_digit = number // 10
        return min(5, max(1, first_digit))

    # For single-digit numbers or other cases, default to year 1
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
        r"^а\.о\.\s*",  # а.о. (assistant)
        r"^а\.о\s+",  # а.о  (with space)
        r"^с\.п\.\.*\s*",  # с.п. and с.п.. (senior lecturer, handles typo)
        r"^с\.п\s+",  # с.п  (with space)
        r"^доцент\s*",  # доцент (associate professor - full)
        r"^д\.\s*",  # д. (abbreviated доцент)
        r"^асс\.проф\.\s*",  # асс.проф. (assistant professor)
        r"^қ\.проф\.\s*",  # қ.проф. (Kazakh: associate professor)
        r"^проф\.\s*",  # проф. (professor - abbreviated)
        r"^профессор\s*",  # профессор (professor - full)
        r"^ст\.преп\.\s*",  # ст.преп. (senior lecturer)
        r"^преподаватель\s*",  # преподаватель (lecturer - full)
        r"^п\.\s*",  # п. (abbreviated преподаватель)
        r"^о\.\s*",  # о. (unknown, found in data)
        # English prefixes
        r"^prof\.\s*",  # prof. (professor)
        r"^Dr\s+",  # Dr (doctor)
    ]
    cleaned = name.strip()
    for prefix in prefixes:
        cleaned = re.sub(prefix, "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def build_subject_prac_lab_hours(streams: list[dict]) -> dict[str, int]:
    """Build a mapping of subject names to their total practical + lab hours.

    Args:
        streams: List of all stream dictionaries from parsed JSON

    Returns:
        Dict mapping subject name to total practical + lab hours
    """
    subject_hours: dict[str, int] = {}
    for stream in streams:
        stream_type = stream.get("stream_type", "")
        if stream_type not in ("practical", "lab"):
            continue

        subject = stream.get("subject", "")
        if not subject:
            continue

        hours = stream.get("hours", {})
        total_hours = hours.get("odd_week", 0) + hours.get("even_week", 0)
        subject_hours[subject] = subject_hours.get(subject, 0) + total_hours

    return subject_hours


def calculate_instructor_available_slots(
    instructor: str,
    shift: Shift,
    instructor_availability: list[dict] | None,
) -> int:
    """Calculate the number of available Stage 1 slots for an instructor.

    Args:
        instructor: Instructor name (may have prefix)
        shift: The shift this stream is taught in
        instructor_availability: List of availability records from JSON

    Returns:
        Number of available slots for Stage 1 days (Mon, Tue, Wed)
    """
    # Get slots for this shift
    shift_slots = FIRST_SHIFT_SLOTS if shift == Shift.FIRST else SECOND_SHIFT_SLOTS

    # Build time -> slot mapping for the shift
    time_to_slot = {}
    for slot_info in TIME_SLOTS:
        if slot_info["slot"] in shift_slots:
            time_to_slot[slot_info["start"]] = slot_info["slot"]

    # Total possible slots = days × slots_per_day
    total_slots = len(STAGE1_DAYS) * len(shift_slots)

    if not instructor_availability:
        return total_slots

    # Clean instructor name
    cleaned_name = clean_instructor_name(instructor)

    # Find instructor's unavailability
    unavailable_count = 0
    for record in instructor_availability:
        if record.get("name") == cleaned_name:
            weekly = record.get("weekly_unavailable", {})
            for day in STAGE1_DAYS:
                day_times = weekly.get(day, [])
                for time in day_times:
                    if time in time_to_slot:  # Only count shift-relevant times
                        unavailable_count += 1
            break

    return total_slots - unavailable_count


def filter_stage1_lectures(
    streams: list[dict],
    instructor_availability: list[dict] | None = None,
) -> list[LectureStream]:
    """Filter and convert streams to LectureStream objects for Stage 1.

    Stage 1 criteria:
    - Type is "lecture"
    - Has at least STAGE1_MIN_GROUPS groups

    Args:
        streams: List of stream dictionaries from parsed JSON
        instructor_availability: List of instructor availability records

    Returns:
        List of LectureStream objects ready for scheduling
    """
    # Pre-compute subject -> prac/lab hours mapping
    subject_prac_lab_hours = build_subject_prac_lab_hours(streams)

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

        subject = stream.get("subject", "")
        instructor = stream.get("instructor", "")

        # Determine shift from groups
        shift = determine_shift(groups)

        # Calculate priority fields
        prac_lab_hours = subject_prac_lab_hours.get(subject, 0)
        available_slots = calculate_instructor_available_slots(
            instructor, shift, instructor_availability
        )

        lecture_stream = LectureStream(
            id=stream.get("id", ""),
            subject=subject,
            instructor=instructor,
            language=stream.get("language", ""),
            groups=groups,
            student_count=stream.get("student_count", 0),
            hours_odd_week=odd_week,
            hours_even_week=even_week,
            shift=shift,
            sheet=stream.get("sheet", ""),
            instructor_available_slots=available_slots,
            subject_prac_lab_hours=prac_lab_hours,
        )
        lecture_streams.append(lecture_stream)

    return lecture_streams


def sort_streams_by_priority(streams: list[LectureStream]) -> list[LectureStream]:
    """Sort streams by scheduling priority.

    Priority order (all factors matter, applied in sequence):
    1. Flexible subjects last (0 = regular, 1 = flexible) - allows filling gaps
    2. Instructor available slots (ascending) - limited availability first
    3. Subject practical/lab hours (descending) - complex subjects first
    4. Student count (descending) - larger streams first

    Args:
        streams: List of LectureStream objects

    Returns:
        Sorted list with highest priority first
    """
    return sorted(
        streams,
        key=lambda s: (
            1 if s.subject in FLEXIBLE_SCHEDULE_SUBJECTS else 0,  # Flexible last
            s.instructor_available_slots,  # Ascending (fewer = higher priority)
            -s.subject_prac_lab_hours,  # Descending (more = higher priority)
            -s.student_count,  # Descending (more = higher priority)
        ),
    )
