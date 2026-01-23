"""Subject configuration loader."""

import json
from pathlib import Path


class SubjectConfig:
    """Loader for subject-specific room requirements."""

    def __init__(self, subject_rooms_path: Path | None = None):
        # subject -> {stream_type: [(address, room)]}
        self._room_requirements: dict[str, dict[str, list[tuple[str, str]]]] = {}

        if subject_rooms_path and subject_rooms_path.exists():
            self._load(subject_rooms_path)

    def _load(self, path: Path) -> None:
        """Load subject room requirements from JSON."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        for subject, requirements in data.items():
            self._room_requirements[subject] = {}

            if "locations" in requirements:
                # General requirement for all types
                locations = [
                    (loc["address"], loc["room"]) for loc in requirements["locations"]
                ]
                self._room_requirements[subject]["lecture"] = locations
                self._room_requirements[subject]["practical"] = locations
                self._room_requirements[subject]["lab"] = locations
            else:
                # Type-specific requirements
                for stream_type in ["lecture", "practice", "lab"]:
                    if stream_type in requirements:
                        locations = [
                            (loc["address"], loc["room"])
                            for loc in requirements[stream_type]
                        ]
                        # Normalize 'practice' to 'practical'
                        key = "practical" if stream_type == "practice" else stream_type
                        self._room_requirements[subject][key] = locations

    def get_required_rooms(
        self, subject: str, stream_type: str
    ) -> list[tuple[str, str]] | None:
        """
        Get required rooms for a subject and stream type.

        Returns list of (address, room) tuples, or None if no restrictions.
        """
        if subject not in self._room_requirements:
            return None
        return self._room_requirements[subject].get(stream_type)

    def has_room_requirement(self, subject: str, stream_type: str) -> bool:
        """Check if subject has room requirements for the given stream type."""
        required = self.get_required_rooms(subject, stream_type)
        return required is not None and len(required) > 0

    def get_all_subjects_with_requirements(self) -> list[str]:
        """Get list of subjects with room requirements."""
        return list(self._room_requirements.keys())
