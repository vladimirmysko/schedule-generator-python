"""Group configuration loader."""

import csv
import json
from pathlib import Path


class GroupConfig:
    """Loader for group-related configurations."""

    def __init__(
        self,
        group_buildings_path: Path | None = None,
        nearby_buildings_path: Path | None = None,
        dead_groups_path: Path | None = None,
        second_shift_path: Path | None = None,
    ):
        # Specialty -> list of allowed addresses
        self._specialty_buildings: dict[str, list[str]] = {}
        # List of nearby building groups (buildings in same group don't need gap)
        self._nearby_groups: list[set[str]] = []
        # Set of dead groups (0 students)
        self._dead_groups: set[str] = set()
        # Set of groups forced to second shift
        self._second_shift_groups: set[str] = set()

        if group_buildings_path and group_buildings_path.exists():
            self._load_specialty_buildings(group_buildings_path)
        if nearby_buildings_path and nearby_buildings_path.exists():
            self._load_nearby_buildings(nearby_buildings_path)
        if dead_groups_path and dead_groups_path.exists():
            self._load_dead_groups(dead_groups_path)
        if second_shift_path and second_shift_path.exists():
            self._load_second_shift(second_shift_path)

    def _load_specialty_buildings(self, path: Path) -> None:
        """Load specialty building assignments from JSON."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        for specialty, config in data.items():
            addresses = [entry["address"] for entry in config.get("addresses", [])]
            if addresses:
                self._specialty_buildings[specialty] = addresses

    def _load_nearby_buildings(self, path: Path) -> None:
        """Load nearby building groups from JSON."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        for group in data.get("groups", []):
            addresses = set(group.get("addresses", []))
            if addresses:
                self._nearby_groups.append(addresses)

    def _load_dead_groups(self, path: Path) -> None:
        """Load dead groups from CSV."""
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("name", "").strip()
                if name:
                    self._dead_groups.add(name)

    def _load_second_shift(self, path: Path) -> None:
        """Load groups forced to second shift from CSV."""
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("name", "").strip()
                if name:
                    self._second_shift_groups.add(name)

    def get_specialty_addresses(self, specialty: str) -> list[str] | None:
        """Get allowed addresses for a specialty (HC-24)."""
        return self._specialty_buildings.get(specialty)

    def is_specialty_exclusive(self, specialty: str) -> bool:
        """Check if a specialty has exclusive building requirements."""
        return specialty in self._specialty_buildings

    def are_buildings_nearby(self, address1: str, address2: str) -> bool:
        """Check if two buildings are in the same nearby group."""
        if address1 == address2:
            return True

        for group in self._nearby_groups:
            if address1 in group and address2 in group:
                return True
        return False

    def is_dead_group(self, group_name: str) -> bool:
        """Check if a group is a dead group (0 students)."""
        return group_name in self._dead_groups

    def is_second_shift_group(self, group_name: str) -> bool:
        """Check if a group is forced to second shift."""
        return group_name in self._second_shift_groups

    def get_all_specialties(self) -> list[str]:
        """Get all specialties with building restrictions."""
        return list(self._specialty_buildings.keys())

    def get_all_dead_groups(self) -> set[str]:
        """Get all dead groups."""
        return self._dead_groups.copy()

    def get_all_second_shift_groups(self) -> set[str]:
        """Get all groups forced to second shift."""
        return self._second_shift_groups.copy()
