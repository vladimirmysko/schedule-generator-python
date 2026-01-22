"""Constants for schedule generation."""

from enum import Enum


class Shift(str, Enum):
    """Shift type."""

    FIRST = "first"
    SECOND = "second"


# Time slots definition
# Each slot is 50 minutes with breaks
TIME_SLOTS = [
    {"slot": 1, "start": "09:00", "end": "09:50", "shift": Shift.FIRST},
    {"slot": 2, "start": "10:00", "end": "10:50", "shift": Shift.FIRST},
    {"slot": 3, "start": "11:00", "end": "11:50", "shift": Shift.FIRST},
    {"slot": 4, "start": "12:00", "end": "12:50", "shift": Shift.FIRST},
    {"slot": 5, "start": "13:00", "end": "13:50", "shift": Shift.FIRST},
    {"slot": 6, "start": "14:00", "end": "14:50", "shift": Shift.SECOND},
    {"slot": 7, "start": "15:00", "end": "15:50", "shift": Shift.SECOND},
    {"slot": 8, "start": "16:00", "end": "16:50", "shift": Shift.SECOND},
    {"slot": 9, "start": "17:00", "end": "17:50", "shift": Shift.SECOND},
    {"slot": 10, "start": "18:00", "end": "18:50", "shift": Shift.SECOND},
    {"slot": 11, "start": "19:00", "end": "19:50", "shift": Shift.SECOND},
    {"slot": 12, "start": "20:00", "end": "20:50", "shift": Shift.SECOND},
    {"slot": 13, "start": "21:00", "end": "21:50", "shift": Shift.SECOND},
]

# Stage 1: Primary days are Monday, Tuesday, Wednesday
STAGE1_DAYS = ["monday", "tuesday", "wednesday"]

# Stage 1: Overflow days when primary days are exhausted
STAGE1_OVERFLOW_DAYS = ["thursday", "friday"]

# Subjects with flexible day scheduling (can be scheduled Mon-Fri with low priority)
# These subjects are scheduled last to fill remaining slots after other subjects
FLEXIBLE_SCHEDULE_SUBJECTS = ["Дене шынықтыру"]

# Minimum groups for Stage 1 lectures
STAGE1_MIN_GROUPS = 2

# Slots by shift
FIRST_SHIFT_SLOTS = [1, 2, 3, 4, 5]
SECOND_SHIFT_SLOTS = [6, 7, 8, 9, 10, 11, 12, 13]

# Extended first shift slots (slots 6-7 can be used when standard slots are insufficient)
# Per CONSTRAINTS.md section 6.3: "Shift Boundary Flexibility"
FIRST_SHIFT_EXTENDED_SLOTS = [1, 2, 3, 4, 5, 6, 7]

# Year to shift mapping
# 1st year: First shift (mandatory)
# 2nd year: Second shift (mandatory)
# 3rd year: First shift (default)
# 4th/5th year: Second shift (default)
YEAR_SHIFT_MAP = {
    1: Shift.FIRST,
    2: Shift.SECOND,
    3: Shift.FIRST,
    4: Shift.SECOND,
    5: Shift.SECOND,
}


def get_slot_info(slot_number: int) -> dict | None:
    """Get slot info by slot number."""
    for slot in TIME_SLOTS:
        if slot["slot"] == slot_number:
            return slot
    return None


def get_slot_time_range(slot_number: int) -> str:
    """Get time range string for a slot (e.g., '09:00-09:50')."""
    slot = get_slot_info(slot_number)
    if slot:
        return f"{slot['start']}-{slot['end']}"
    return ""


def get_slots_for_shift(shift: Shift, extended: bool = False) -> list[int]:
    """Get slot numbers for a shift.

    Args:
        shift: The shift type (FIRST or SECOND)
        extended: If True and shift is FIRST, returns extended slots (1-7)
                  per CONSTRAINTS.md section 6.3 "Shift Boundary Flexibility"

    Returns:
        List of valid slot numbers for the shift
    """
    if shift == Shift.FIRST:
        return FIRST_SHIFT_EXTENDED_SLOTS if extended else FIRST_SHIFT_SLOTS
    return SECOND_SHIFT_SLOTS


def get_slot_start_time(slot_number: int) -> str:
    """Get start time for a slot (e.g., slot 1 → '09:00').

    Args:
        slot_number: Slot number (1-13)

    Returns:
        Start time string in HH:MM format, or empty string if slot not found
    """
    slot = get_slot_info(slot_number)
    if slot:
        return slot["start"]
    return ""
