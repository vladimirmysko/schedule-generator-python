"""Room configuration loader."""

import csv
from pathlib import Path

from ..models import Room


class RoomConfig:
    """Loader for room configuration from rooms.csv."""

    def __init__(self, rooms_path: Path | None = None):
        self.rooms: list[Room] = []
        self._by_name_address: dict[tuple[str, str], Room] = {}
        self._by_address: dict[str, list[Room]] = {}

        if rooms_path and rooms_path.exists():
            self._load(rooms_path)

    def _load(self, path: Path) -> None:
        """Load rooms from CSV file."""
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                room = Room(
                    name=row["name"].strip(),
                    capacity=int(row["capacity"]),
                    address=row["address"].strip(),
                    is_special=row.get("is_special", "").lower() == "true",
                )
                self.rooms.append(room)
                self._by_name_address[(room.name, room.address)] = room

                if room.address not in self._by_address:
                    self._by_address[room.address] = []
                self._by_address[room.address].append(room)

    def get_room(self, name: str, address: str) -> Room | None:
        """Get a room by name and address."""
        return self._by_name_address.get((name, address))

    def get_rooms_at_address(self, address: str) -> list[Room]:
        """Get all rooms at a given address."""
        return self._by_address.get(address, [])

    def get_all_rooms(self) -> list[Room]:
        """Get all rooms."""
        return self.rooms

    def get_regular_rooms(self) -> list[Room]:
        """Get all non-special rooms."""
        return [r for r in self.rooms if not r.is_special]

    def get_special_rooms(self) -> list[Room]:
        """Get all special rooms."""
        return [r for r in self.rooms if r.is_special]

    def get_rooms_by_capacity(self, min_capacity: int) -> list[Room]:
        """Get rooms with at least the given capacity."""
        return [r for r in self.rooms if r.capacity >= min_capacity]

    def get_all_addresses(self) -> set[str]:
        """Get all unique building addresses."""
        return set(self._by_address.keys())
