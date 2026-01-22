"""Name normalization utilities for instructor and entity names."""

import re

import pandas as pd

# Common academic prefixes to remove from instructor names
INSTRUCTOR_PREFIX_PATTERNS = [
    # Russian academic prefixes
    r"^а\.о\.\s*",  # а.о. (assistant) - handles "а.о." and "а.о. "
    r"^а\.о\s+",  # а.о  (no period, with space)
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


def normalize_instructor_name(name: str) -> str:
    """Normalize instructor name by removing prefixes and extra whitespace.

    This function ensures that instructor names like "а.о. Шалаев Б.Б." and
    "а.о.Шалаев Б.Б." are normalized to the same value "Шалаев Б.Б.".

    Args:
        name: Raw instructor name with potential prefixes

    Returns:
        Cleaned instructor name without prefixes and with normalized whitespace
    """
    if not name or pd.isna(name):
        return ""

    cleaned = str(name).strip()

    # Remove academic prefixes
    for prefix_pattern in INSTRUCTOR_PREFIX_PATTERNS:
        cleaned = re.sub(prefix_pattern, "", cleaned, flags=re.IGNORECASE)

    # Normalize whitespace (collapse multiple spaces to single space)
    cleaned = " ".join(cleaned.split())

    return cleaned.strip()
