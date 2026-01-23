"""Constants for the university course scheduling system."""

from enum import Enum
from typing import Final


class Shift(Enum):
    """Academic shift (first or second half of day)."""

    FIRST = 1  # Slots 1-5 (9:00-14:00)
    SECOND = 2  # Slots 6-13 (14:00-21:50)


# Time slot configuration
MIN_SLOT: Final[int] = 1
MAX_SLOT: Final[int] = 13

# Shift boundaries
FIRST_SHIFT_SLOTS: Final[tuple[int, ...]] = (1, 2, 3, 4, 5)
SECOND_SHIFT_SLOTS: Final[tuple[int, ...]] = (6, 7, 8, 9, 10, 11, 12, 13)

# Extended first shift (when needed)
EXTENDED_FIRST_SHIFT_SLOTS: Final[tuple[int, ...]] = (1, 2, 3, 4, 5, 6, 7)

# Time slot to clock time mapping
SLOT_TIMES: Final[dict[int, str]] = {
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

# Subjects with flexible scheduling (can use Mon-Fri instead of Mon-Wed)
FLEXIBLE_SCHEDULE_SUBJECTS: Final[tuple[str, ...]] = ("Дене шынықтыру",)

# Primary and overflow days for regular subjects
PRIMARY_DAYS: Final[tuple[str, ...]] = ("monday", "tuesday", "wednesday")
OVERFLOW_DAYS: Final[tuple[str, ...]] = ("thursday", "friday")

# Daily load constraints (HC-16)
MIN_DAILY_LESSONS: Final[int] = 2
PREFERRED_DAILY_LESSONS: Final[int] = 3
MAX_DAILY_LESSONS: Final[int] = 6

# Maximum windows per day (HC-18)
MAX_WINDOWS_PER_DAY: Final[int] = 1

# Room capacity buffer (HC-04)
SMALL_STREAM_THRESHOLD: Final[int] = 30
LARGE_STREAM_THRESHOLD: Final[int] = 100
SMALL_STREAM_BUFFER: Final[float] = 0.5  # 50%
LARGE_STREAM_BUFFER: Final[float] = 0.2  # 20%

# Special room names
SPECIAL_ROOMS: Final[tuple[str, ...]] = ("IT Group", "Спорт зал", "AVENCOM", "БҚВҒЗС")

# Specialty codes with building exclusivity (HC-24)
SPECIALTY_BUILDINGS: Final[dict[str, str]] = {
    "ВЕТ": "ул. Жангир хана, 51/4",
    "СТР": "ул. Чапаева 69",
    "АРХ": "ул. Чапаева 69",
    "ЗК": "ул. Чапаева 69",
    "ЮР": "ул. Победа, 137/1",
}

# Soft constraint weights (SC-01 to SC-22)
SOFT_CONSTRAINT_WEIGHTS: Final[dict[str, int]] = {
    "SC-01": 180,  # Required sessions target
    "SC-02": 150,  # Student gaps
    "SC-03": 60,  # Balanced load
    "SC-04": 70,  # Late-early sequence
    "SC-05": 30,  # Start consistency
    "SC-06": 120,  # Building transitions
    "SC-07": 80,  # Instructor gaps
    "SC-08": 60,  # Instructor time pref
    "SC-09": 40,  # Instructor day pref
    "SC-10": 70,  # Daily teaching load
    "SC-11": 100,  # Part-time grouping
    "SC-12": 75,  # Instructor room pref
    "SC-13": 30,  # Room capacity fit
    "SC-14": 20,  # Room fragmentation
    "SC-15": 75,  # Lecture-practical order
    "SC-16": 65,  # Lab distribution
    "SC-17": 45,  # Difficult subject timing
    "SC-18": 55,  # Meeting blocks
    "SC-19": 100,  # Elective accessibility
    "SC-20": 35,  # Section balance
    "SC-21": 20,  # State language priority
    "SC-22": 15,  # Climate considerations
}

# Default solver timeout in seconds
DEFAULT_TIME_LIMIT: Final[int] = 300

# Target scheduling rate
TARGET_SCHEDULING_RATE: Final[float] = 0.85  # 85%
