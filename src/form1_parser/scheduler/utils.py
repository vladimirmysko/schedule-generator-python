"""Utility functions for the scheduler."""

import re
from typing import Any

from .constants import (
    FIRST_SHIFT_SLOTS,
    FLEXIBLE_SCHEDULE_SUBJECTS,
    LARGE_STREAM_BUFFER,
    LARGE_STREAM_THRESHOLD,
    SECOND_SHIFT_SLOTS,
    SMALL_STREAM_BUFFER,
    SMALL_STREAM_THRESHOLD,
    Shift,
)
from .models import Day, LectureStream, StreamType


def parse_group_year(group_name: str) -> int | None:
    """
    Extract year from group code.

    Group names follow patterns like:
    - "АРХ-21 О" -> year 2 (first digit of 2-digit number after hyphen)
    - "ЮР-17 О" -> year 1
    - "СТР-31 О" -> year 3

    Returns None if year cannot be determined.
    """
    # Match pattern: LETTERS-DIGITS (e.g., АРХ-21)
    match = re.search(r"-(\d)", group_name)
    if match:
        return int(match.group(1))
    return None


def parse_specialty_code(group_name: str) -> str | None:
    """
    Extract specialty prefix from group code.

    Examples:
    - "АРХ-21 О" -> "АРХ"
    - "ВЕТ-31 О" -> "ВЕТ"
    - "ЮР-17 О /у/" -> "ЮР"
    """
    # Match Cyrillic letters before hyphen
    match = re.match(r"^([А-ЯЁа-яё]+)", group_name)
    if match:
        return match.group(1).upper()
    return None


def get_all_specialties(groups: list[str]) -> set[str]:
    """Get all unique specialties from a list of groups."""
    specialties = set()
    for group in groups:
        specialty = parse_specialty_code(group)
        if specialty:
            specialties.add(specialty)
    return specialties


def is_same_specialty_stream(groups: list[str]) -> bool:
    """
    Check if all groups in a stream belong to the same specialty.

    This is used for specialty building exclusivity (HC-24).
    """
    specialties = get_all_specialties(groups)
    return len(specialties) == 1


def clean_instructor_name(name: str) -> str:
    """
    Remove academic title prefixes from instructor name.

    Examples:
    - "а.о. Утебалиев М.М." -> "Утебалиев М.М."
    - "с.п.Уахасов Қ.С." -> "Уахасов Қ.С."
    - "проф. Иванов И.И." -> "Иванов И.И."
    """
    # Common prefixes (in Kazakh and Russian)
    prefixes = [
        r"а\.о\.\s*",  # аға оқытушы
        r"с\.п\.\s*",  # старший преподаватель
        r"о\.\s*",  # оқытушы
        r"п\.\s*",  # преподаватель
        r"қ\.проф\.\s*",  # қауымдастырылған профессор
        r"асс\.проф\.\s*",  # ассоциированный профессор
        r"проф\.\s*",  # профессор
        r"д\.\s*",  # доктор
        r"prof\.\s*",  # professor
    ]
    pattern = "^(" + "|".join(prefixes) + ")"
    cleaned = re.sub(pattern, "", name, flags=re.IGNORECASE)
    return cleaned.strip()


def determine_shift(year: int | None) -> Shift:
    """
    Determine the shift for a given year.

    Rules (HC-11):
    - 1st year: First shift (always)
    - 2nd year: Second shift (always)
    - 3rd year: First shift (with exceptions)
    - 4th/5th year: Automatic (algorithm selects)

    For automatic selection, we default to second shift.
    """
    if year is None:
        return Shift.SECOND  # Default to second shift if unknown
    if year == 1:
        return Shift.FIRST
    elif year == 2:
        return Shift.SECOND
    elif year == 3:
        return Shift.FIRST  # With exceptions handled elsewhere
    else:  # 4th, 5th year
        return Shift.SECOND  # Default for automatic selection


def get_shift_for_groups(groups: list[str]) -> Shift:
    """
    Determine the shift based on group years.

    If groups have mixed years, prefer the shift of the majority.
    If there's a tie, prefer second shift (more slots available).
    """
    years = [parse_group_year(g) for g in groups]
    valid_years = [y for y in years if y is not None]

    if not valid_years:
        return Shift.SECOND

    shifts = [determine_shift(y) for y in valid_years]
    first_count = sum(1 for s in shifts if s == Shift.FIRST)
    second_count = len(shifts) - first_count

    if first_count > second_count:
        return Shift.FIRST
    return Shift.SECOND


def get_slots_for_shift(shift: Shift) -> tuple[int, ...]:
    """Get the valid slots for a given shift."""
    if shift == Shift.FIRST:
        return FIRST_SHIFT_SLOTS
    return SECOND_SHIFT_SLOTS


def calculate_capacity_buffer(student_count: int) -> int:
    """
    Calculate the capacity buffer based on stream size (HC-04).

    - Small streams (<=30): 50% buffer
    - Large streams (>=100): 20% buffer
    - In between: linear interpolation
    """
    if student_count <= SMALL_STREAM_THRESHOLD:
        buffer_pct = SMALL_STREAM_BUFFER
    elif student_count >= LARGE_STREAM_THRESHOLD:
        buffer_pct = LARGE_STREAM_BUFFER
    else:
        # Linear interpolation
        range_size = LARGE_STREAM_THRESHOLD - SMALL_STREAM_THRESHOLD
        position = (student_count - SMALL_STREAM_THRESHOLD) / range_size
        buffer_pct = SMALL_STREAM_BUFFER - position * (
            SMALL_STREAM_BUFFER - LARGE_STREAM_BUFFER
        )

    return int(student_count * buffer_pct)


def get_effective_capacity(room_capacity: int, student_count: int) -> int:
    """Get effective room capacity with buffer applied."""
    buffer = calculate_capacity_buffer(student_count)
    return room_capacity + buffer


def is_flexible_subject(subject: str) -> bool:
    """Check if a subject has flexible scheduling (can use any weekday)."""
    return subject in FLEXIBLE_SCHEDULE_SUBJECTS


def filter_stage1_lectures(streams: list[dict[str, Any]]) -> list[LectureStream]:
    """
    Filter streams to get only lectures with 2+ groups for Stage 1 scheduling.

    Stage 1 focuses on multi-group lectures (Monday-Wednesday).
    """
    result = []
    for stream in streams:
        if stream.get("stream_type") != "lecture":
            continue
        groups = stream.get("groups", [])
        if len(groups) < 2:
            continue
        result.append(LectureStream.from_dict(stream))
    return result


def sort_streams_by_priority(streams: list[LectureStream]) -> list[LectureStream]:
    """
    Sort streams by scheduling priority.

    Priority order (higher = scheduled first):
    1. Larger student count (harder to fit)
    2. More hours (more constraints)
    3. Non-flexible subjects before flexible ones
    4. Regular subjects before flexible (PE) subjects
    """

    def priority_key(stream: LectureStream) -> tuple[bool, int, int]:
        is_flex = is_flexible_subject(stream.subject)
        return (is_flex, -stream.student_count, -max(stream.hours_odd, stream.hours_even))

    return sorted(streams, key=priority_key)


def time_to_slot(time_str: str) -> int | None:
    """
    Convert time string to slot number.

    Examples:
    - "09:00" -> 1
    - "14:00" -> 6
    - "21:00" -> 13
    """
    time_to_slot_map = {
        "09:00": 1,
        "10:00": 2,
        "11:00": 3,
        "12:00": 4,
        "13:00": 5,
        "14:00": 6,
        "15:00": 7,
        "16:00": 8,
        "17:00": 9,
        "18:00": 10,
        "19:00": 11,
        "20:00": 12,
        "21:00": 13,
    }
    return time_to_slot_map.get(time_str)


def slot_to_time(slot: int) -> str | None:
    """Convert slot number to time string."""
    slot_to_time_map = {
        1: "09:00",
        2: "10:00",
        3: "11:00",
        4: "12:00",
        5: "13:00",
        6: "14:00",
        7: "15:00",
        8: "16:00",
        9: "17:00",
        10: "18:00",
        11: "19:00",
        12: "20:00",
        13: "21:00",
    }
    return slot_to_time_map.get(slot)


def day_name_to_enum(day_name: str) -> Day | None:
    """Convert day name string to Day enum."""
    mapping = {
        "monday": Day.MONDAY,
        "tuesday": Day.TUESDAY,
        "wednesday": Day.WEDNESDAY,
        "thursday": Day.THURSDAY,
        "friday": Day.FRIDAY,
        "saturday": Day.SATURDAY,
    }
    return mapping.get(day_name.lower())
