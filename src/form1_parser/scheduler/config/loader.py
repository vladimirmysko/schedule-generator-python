"""Unified configuration loader."""

from pathlib import Path

from .groups import GroupConfig
from .instructors import InstructorConfig
from .rooms import RoomConfig
from .subjects import SubjectConfig


class ConfigLoader:
    """Unified loader for all scheduling configuration files."""

    def __init__(
        self,
        config_dir: Path | None = None,
        rooms_csv: Path | None = None,
    ):
        """
        Initialize configuration loader.

        Args:
            config_dir: Path to directory containing configuration files.
                       Expected files:
                       - rooms.csv
                       - instructor-availability.json
                       - instructor-rooms.json
                       - instructor-days.json
                       - subject-rooms.json
                       - group-buildings.json
                       - nearby-buildings.json
                       - dead-groups.csv
                       - groups-second-shift.csv
            rooms_csv: Direct path to rooms.csv (for backwards compatibility).
                      If provided, overrides rooms.csv from config_dir.
        """
        if config_dir is None:
            config_dir = Path("reference")

        self.config_dir = Path(config_dir)

        # Determine rooms.csv path
        rooms_path = rooms_csv if rooms_csv else self._get_path("rooms.csv")

        # Initialize sub-loaders
        self.rooms = RoomConfig(rooms_path)
        self.instructors = InstructorConfig(
            availability_path=self._get_path("instructor-availability.json"),
            rooms_path=self._get_path("instructor-rooms.json"),
            days_path=self._get_path("instructor-days.json"),
        )
        self.subjects = SubjectConfig(self._get_path("subject-rooms.json"))
        self.groups = GroupConfig(
            group_buildings_path=self._get_path("group-buildings.json"),
            nearby_buildings_path=self._get_path("nearby-buildings.json"),
            dead_groups_path=self._get_path("dead-groups.csv"),
            second_shift_path=self._get_path("groups-second-shift.csv"),
        )

    def _get_path(self, filename: str) -> Path | None:
        """Get path to config file if it exists."""
        path = self.config_dir / filename
        return path if path.exists() else None
