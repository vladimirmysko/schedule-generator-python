"""Constants for Form-1 parser."""

# Column indices (0-based)
COL_NUMBER = 0
COL_SUBJECT = 1
COL_SPECIALTY = 3
COL_GROUP = 4
COL_CREDITS = 5
COL_LANGUAGE = 6
COL_STUDENTS = 7
COL_LECTURES = 8
COL_PRACTICALS = 9
COL_LABS = 10

# Regex patterns
EXPLICIT_SUBGROUP_PATTERN = r"/[12]/|\\[12]\\|\s-[12]$"
STUDY_FORM_PATTERN = r"/[уг]/"
GROUP_NAME_PATTERN = r"^[А-ЯӘҒҚҢӨҰҮІа-яәғқңөұүі]+-\d{2}"

# Instructor detection markers
INSTRUCTOR_MARKERS = ["проф", "а.о.", "с.п.", "асс", "доц"]

# Data start markers
DATA_START_MARKERS = ["1", "2 семестр", "2семестр"]

# Languages
LANGUAGE_KAZAKH = "каз"
LANGUAGE_RUSSIAN = "орыс"
VALID_LANGUAGES = {LANGUAGE_KAZAKH, LANGUAGE_RUSSIAN}

# Sheet names
SHEET_NAMES = ["оод (2)", "эиб", "юр", "стр", "эл", "ттт", "нд"]

# Known instructor column positions per sheet
KNOWN_INSTRUCTOR_COLUMNS = {
    "оод (2)": 25,
    "эиб": 25,
    "юр": 25,
    "стр": 26,
    "эл": 25,
    "ттт": 25,
    "нд": 26,
}

# Academic weeks
ODD_WEEKS_COUNT = 8  # 1, 3, 5, 7, 9, 11, 13, 15
EVEN_WEEKS_COUNT = 7  # 2, 4, 6, 8, 10, 12, 14
TOTAL_WEEKS = ODD_WEEKS_COUNT + EVEN_WEEKS_COUNT  # 15

# Pattern names
PATTERN_1A = "1a"
PATTERN_1B = "1b"
PATTERN_IMPLICIT_SUBGROUP = "implicit_subgroup"
PATTERN_EXPLICIT_SUBGROUP = "explicit_subgroup"
