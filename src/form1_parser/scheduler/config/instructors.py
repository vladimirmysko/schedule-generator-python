"""Instructor configuration loader."""

import json
from pathlib import Path
from typing import Any

from ..models import Day
from ..utils import clean_instructor_name, day_name_to_enum, time_to_slot


class InstructorConfig:
    """Loader for instructor configurations."""

    def __init__(
        self,
        availability_path: Path | None = None,
        rooms_path: Path | None = None,
        days_path: Path | None = None,
    ):
        # Availability: instructor -> {day: set of unavailable slots}
        self._availability: dict[str, dict[Day, set[int]]] = {}
        # Room preferences: instructor -> {stream_type: [(address, room)]}
        self._room_preferences: dict[str, dict[str, list[tuple[str, str]]]] = {}
        # Day constraints: instructor -> {year: [allowed days]}
        self._day_constraints: dict[str, dict[int, list[Day]]] = {}
        # One day per week flag
        self._one_day_per_week: set[str] = set()

        if availability_path and availability_path.exists():
            self._load_availability(availability_path)
        if rooms_path and rooms_path.exists():
            self._load_rooms(rooms_path)
        if days_path and days_path.exists():
            self._load_days(days_path)

    def _normalize_name(self, name: str) -> str:
        """Normalize instructor name for matching."""
        return clean_instructor_name(name).strip()

    def _load_availability(self, path: Path) -> None:
        """Load instructor availability from JSON."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        for entry in data:
            name = self._normalize_name(entry["name"])
            weekly_unavailable = entry.get("weekly_unavailable", {})

            self._availability[name] = {}
            for day_name, times in weekly_unavailable.items():
                day = day_name_to_enum(day_name)
                if day is None:
                    continue

                slots = set()
                for time_str in times:
                    slot = time_to_slot(time_str)
                    if slot is not None:
                        slots.add(slot)

                if slots:
                    self._availability[name][day] = slots

    def _load_rooms(self, path: Path) -> None:
        """Load instructor room preferences from JSON."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        for name, prefs in data.items():
            normalized_name = self._normalize_name(name)
            self._room_preferences[normalized_name] = {}

            # Handle different formats
            if "locations" in prefs:
                # General preference for all types
                locations = [
                    (loc["address"], loc["room"]) for loc in prefs["locations"]
                ]
                self._room_preferences[normalized_name]["lecture"] = locations
                self._room_preferences[normalized_name]["practical"] = locations
                self._room_preferences[normalized_name]["lab"] = locations
            else:
                # Type-specific preferences
                for stream_type in ["lecture", "practice", "lab"]:
                    if stream_type in prefs:
                        locations = [
                            (loc["address"], loc["room"]) for loc in prefs[stream_type]
                        ]
                        # Normalize 'practice' to 'practical'
                        key = "practical" if stream_type == "practice" else stream_type
                        self._room_preferences[normalized_name][key] = locations

    def _load_days(self, path: Path) -> None:
        """Load instructor day constraints from JSON."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        for entry in data:
            name = self._normalize_name(entry["name"])
            year_days = entry.get("year_days", {})

            self._day_constraints[name] = {}
            for year_str, day_names in year_days.items():
                year = int(year_str)
                days = []
                for day_name in day_names:
                    day = day_name_to_enum(day_name)
                    if day is not None:
                        days.append(day)
                if days:
                    self._day_constraints[name][year] = days

            if entry.get("one_day_per_week", False):
                self._one_day_per_week.add(name)

    def is_available(self, instructor: str, day: Day, slot: int) -> bool:
        """Check if instructor is available at the given day/slot."""
        name = self._normalize_name(instructor)
        if name not in self._availability:
            return True  # No restrictions

        day_unavailable = self._availability[name].get(day, set())
        return slot not in day_unavailable

    def get_unavailable_slots(self, instructor: str, day: Day) -> set[int]:
        """Get unavailable slots for instructor on a given day."""
        name = self._normalize_name(instructor)
        if name not in self._availability:
            return set()
        return self._availability[name].get(day, set())

    def get_room_preferences(
        self, instructor: str, stream_type: str
    ) -> list[tuple[str, str]]:
        """
        Get room preferences for instructor and stream type.

        Returns list of (address, room) tuples.
        """
        name = self._normalize_name(instructor)
        prefs = self._room_preferences.get(name, {})
        return prefs.get(stream_type, [])

    def get_allowed_days_for_year(self, instructor: str, year: int) -> list[Day] | None:
        """
        Get allowed days for instructor to teach a specific year.

        Returns None if no restrictions (all days allowed).
        """
        name = self._normalize_name(instructor)
        if name not in self._day_constraints:
            return None
        return self._day_constraints[name].get(year)

    def requires_one_day_per_week(self, instructor: str) -> bool:
        """Check if instructor requires all classes on the same day."""
        name = self._normalize_name(instructor)
        return name in self._one_day_per_week

    def get_all_instructors_with_availability(self) -> list[str]:
        """Get list of instructors with availability constraints."""
        return list(self._availability.keys())
