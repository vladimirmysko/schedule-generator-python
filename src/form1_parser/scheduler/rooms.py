"""Room management for schedule generation."""

import csv
import re
from collections import defaultdict
from pathlib import Path

from ..normalization import normalize_instructor_name
from .models import (
    Day,
    LectureStream,
    PracticalStream,
    Room,
    Stage3PracticalStream,
    Stage4LectureStream,
    Stage5PracticalStream,
    Stage6LabStream,
    WeekType,
)


class RoomManager:
    """Manages room assignments with priority-based selection.

    Priority order for finding rooms:
    0. Instructor special rooms (is_special=True, highest priority)
    1. Subject-specific rooms (from subject-rooms.json)
    2. Instructor non-special room preferences (from instructor-rooms.json)
    3. Group building preferences (from group-buildings.json)
    4. General pool - find by capacity
    """

    def __init__(
        self,
        rooms_csv: Path,
        subject_rooms: dict | None = None,
        instructor_rooms: dict | None = None,
        group_buildings: dict | None = None,
        stream_address_exclusions: dict | None = None,
    ) -> None:
        """Initialize the room manager.

        Args:
            rooms_csv: Path to rooms.csv file
            subject_rooms: Dictionary from subject-rooms.json
            instructor_rooms: Dictionary from instructor-rooms.json
            group_buildings: Dictionary from group-buildings.json
            stream_address_exclusions: Dictionary mapping stream_id -> list of excluded addresses
        """
        self.rooms = self._load_rooms(rooms_csv)
        self.subject_rooms = subject_rooms or {}
        self.instructor_rooms = instructor_rooms or {}
        self.group_buildings = group_buildings or {}
        self.stream_address_exclusions = stream_address_exclusions or {}
        # (day, slot, week_type) -> set of room names
        self.room_schedule: dict[tuple[Day, int, WeekType], set[str]] = defaultdict(set)
        # Build set of reserved addresses and their allowed specialties
        self._reserved_addresses = self._build_reserved_addresses()

    def _is_address_excluded_for_stream(self, stream_id: str, address: str) -> bool:
        """Check if an address is excluded for a specific stream.

        Args:
            stream_id: Stream ID to check
            address: Address to check

        Returns:
            True if the address is excluded for this stream
        """
        if stream_id not in self.stream_address_exclusions:
            return False
        excluded_addresses = self.stream_address_exclusions[stream_id]
        return address in excluded_addresses

    def _build_reserved_addresses(self) -> dict[str, set[str]]:
        """Build mapping of reserved addresses to allowed specialties.

        Returns:
            Dict mapping address -> set of specialty codes that can use it
        """
        reserved: dict[str, set[str]] = {}
        for specialty, config in self.group_buildings.items():
            for addr_config in config.get("addresses", []):
                address = addr_config.get("address", "")
                if address:
                    if address not in reserved:
                        reserved[address] = set()
                    reserved[address].add(specialty)
        return reserved

    def _load_rooms(self, rooms_csv: Path) -> list[Room]:
        """Load rooms from CSV file.

        Args:
            rooms_csv: Path to rooms.csv file

        Returns:
            List of Room objects
        """
        rooms = []
        with open(rooms_csv, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("name", "").strip()
                if not name:
                    continue

                capacity_str = row.get("capacity", "0").strip()
                capacity = int(capacity_str) if capacity_str else 0

                address = row.get("address", "").strip()
                is_special_str = row.get("is_special", "").strip().lower()
                is_special = is_special_str == "true"

                rooms.append(
                    Room(
                        name=name,
                        capacity=capacity,
                        address=address,
                        is_special=is_special,
                    )
                )
        return rooms

    def _clean_instructor_name(self, name: str) -> str:
        """Clean instructor name by removing prefixes like 'а.о.', 'с.п.', etc.

        Args:
            name: Original instructor name

        Returns:
            Cleaned instructor name
        """
        return normalize_instructor_name(name)

    def _get_subject_rooms(self, subject: str, class_type: str) -> list[Room]:
        """Get allowed rooms for a subject and class type.

        Args:
            subject: Subject name
            class_type: Type of class ('lecture', 'practice', 'lab')

        Returns:
            List of Room objects allowed for this subject
        """
        if subject not in self.subject_rooms:
            return []

        subject_config = self.subject_rooms[subject]

        # Try specific class type first
        locations = subject_config.get(class_type, [])

        # Fall back to 'locations' if no specific type
        if not locations:
            locations = subject_config.get("locations", [])

        allowed_rooms = []
        for loc in locations:
            address = loc.get("address", "")
            room_name = loc.get("room", "")

            if room_name:
                # Specific room specified - find exact match
                for room in self.rooms:
                    if room.name == room_name and room.address == address:
                        allowed_rooms.append(room)
                        break
            else:
                # Only address specified - all rooms at this address are allowed
                for room in self.rooms:
                    if room.address == address:
                        allowed_rooms.append(room)

        return allowed_rooms

    def _get_instructor_rooms(self, instructor: str, class_type: str) -> list[Room]:
        """Get preferred rooms for an instructor and class type.

        Args:
            instructor: Instructor name (cleaned)
            class_type: Type of class ('lecture', 'practice', 'lab')

        Returns:
            List of Room objects preferred by this instructor
        """
        if instructor not in self.instructor_rooms:
            return []

        instructor_config = self.instructor_rooms[instructor]

        # Try specific class type first
        locations = instructor_config.get(class_type, [])

        # Fall back to 'locations' if no specific type
        if not locations:
            locations = instructor_config.get("locations", [])

        preferred_rooms = []
        for loc in locations:
            address = loc.get("address", "")
            room_name = loc.get("room", "")
            # Find matching room in our room list
            for room in self.rooms:
                if room.name == room_name and room.address == address:
                    preferred_rooms.append(room)
                    break

        return preferred_rooms

    def _get_instructor_special_rooms(self, instructor: str, class_type: str) -> list[Room]:
        """Get special rooms (is_special=True) preferred by an instructor.

        Args:
            instructor: Instructor name (cleaned)
            class_type: Type of class ('lecture', 'practice', 'lab')

        Returns:
            List of Room objects that are both preferred by instructor and marked special
        """
        all_instructor_rooms = self._get_instructor_rooms(instructor, class_type)
        return [r for r in all_instructor_rooms if r.is_special]

    def _parse_group_specialty(self, group_name: str) -> str:
        """Extract specialty prefix from group name.

        Args:
            group_name: Group name like "АРХ-21 О"

        Returns:
            Specialty code like "АРХ"
        """
        match = re.match(r"([А-ЯA-Z]+)", group_name)
        return match.group(1) if match else ""

    def _get_stream_specialties(self, groups: list[str]) -> set[str]:
        """Get all unique specialties from a list of groups.

        Args:
            groups: List of group names

        Returns:
            Set of specialty codes
        """
        specialties = set()
        for group in groups:
            specialty = self._parse_group_specialty(group)
            if specialty:
                specialties.add(specialty)
        return specialties

    def _is_address_allowed_for_groups(self, address: str, groups: list[str]) -> bool:
        """Check if an address can be used by the given groups.

        Reserved addresses can only be used by their designated specialties.
        Non-reserved addresses can be used by anyone.

        Args:
            address: Building address
            groups: List of group names

        Returns:
            True if the address can be used, False otherwise
        """
        if address not in self._reserved_addresses:
            # Not a reserved address - anyone can use it
            return True

        # Reserved address - check if stream's specialties are allowed
        allowed_specialties = self._reserved_addresses[address]
        stream_specialties = self._get_stream_specialties(groups)

        # All stream specialties must be in allowed specialties
        return stream_specialties.issubset(allowed_specialties)

    def _parse_group_year(self, group_name: str) -> int:
        """Extract year from group name.

        The first digit of the two-digit number indicates the year:
        - 1x (11, 13, 15...) = 1st year
        - 2x (21, 23, 25...) = 2nd year
        - 3x (31, 33, 35...) = 3rd year
        - 4x (41, 43, 45...) = 4th year
        - 5x (51, 53, 55...) = 5th year

        Args:
            group_name: Group name like "АРХ-21 О"

        Returns:
            Year number (1-5), defaults to 0 if unable to parse
        """
        match = re.search(r"-(\d+)", group_name)
        if not match:
            return 0
        number = int(match.group(1))
        # For two-digit numbers, the first digit indicates the year
        if 10 <= number <= 59:
            return number // 10
        return 0

    def _get_group_building_rooms(self, groups: list[str]) -> list[Room]:
        """Get preferred rooms based on group building preferences.

        Only applies if ALL groups in the stream belong to the same specialty
        that has a building preference configured.

        Args:
            groups: List of group names

        Returns:
            List of Room objects in preferred buildings for this group
        """
        if not groups or not self.group_buildings:
            return []

        # Get specialty of first group
        first_specialty = self._parse_group_specialty(groups[0])
        if not first_specialty:
            return []

        # Check if ALL groups belong to the same specialty
        for group in groups[1:]:
            specialty = self._parse_group_specialty(group)
            if specialty != first_specialty:
                return []  # Mixed specialties - no building preference applies

        # Check if this specialty has building preferences
        if first_specialty not in self.group_buildings:
            return []

        config = self.group_buildings[first_specialty]

        # Get preferred addresses
        addresses_config = config.get("addresses", [])
        preferred_addresses = set()
        specific_rooms = {}  # address -> list of room names (if specified)

        for addr_config in addresses_config:
            address = addr_config.get("address", "")
            if address:
                preferred_addresses.add(address)
                # Check if specific rooms are listed
                rooms_list = addr_config.get("rooms", [])
                if rooms_list:
                    specific_rooms[address] = rooms_list

        # Find all rooms in preferred buildings
        preferred_rooms = []
        for room in self.rooms:
            if room.address in preferred_addresses:
                # If specific rooms are defined for this address, check them
                if room.address in specific_rooms:
                    if room.name in specific_rooms[room.address]:
                        preferred_rooms.append(room)
                else:
                    # No specific rooms - all rooms in this building are allowed
                    preferred_rooms.append(room)

        return preferred_rooms

    def _is_room_occupied(
        self, room: Room, day: Day, slot: int, week_type: WeekType = WeekType.BOTH
    ) -> bool:
        """Check if a room is occupied at a given time.

        Args:
            room: Room to check
            day: Day of the week
            slot: Slot number
            week_type: Week type to check

        Returns:
            True if the room is occupied, False otherwise
        """
        key = (day, slot, week_type)
        if room.name in self.room_schedule[key]:
            return True

        # If checking BOTH weeks, also check ODD and EVEN separately
        if week_type == WeekType.BOTH:
            if room.name in self.room_schedule[(day, slot, WeekType.ODD)]:
                return True
            if room.name in self.room_schedule[(day, slot, WeekType.EVEN)]:
                return True

        # If checking specific week, also check BOTH
        if week_type in (WeekType.ODD, WeekType.EVEN):
            if room.name in self.room_schedule[(day, slot, WeekType.BOTH)]:
                return True

        return False

    def _calculate_buffer(self, stream_size: int) -> int:
        """Calculate capacity buffer based on stream size.

        Buffer is added to room capacity when no exact-fit room is available.
        Buffer: 50% for small (<=30), 20% for large (>=100), linear between.

        Example: 30 students, rooms with 18, 16, 14, 12 seats.
        Buffer = 30 * 0.5 = 15
        Effective capacities: 18+15=33, 16+15=31, 14+15=29, 12+15=27
        Rooms with 18 and 16 seats qualify (33>=30, 31>=30).
        Select 18-seat room (largest among qualifying).

        Args:
            stream_size: Number of students in the stream

        Returns:
            Capacity buffer to add to room capacity
        """
        if stream_size <= 30:
            return int(stream_size * 0.5)
        elif stream_size >= 100:
            return int(stream_size * 0.2)
        else:
            # Linear interpolation between 50% at 30 students and 20% at 100 students
            ratio = (stream_size - 30) / 70
            buffer_pct = 0.5 - (ratio * 0.3)
            return int(stream_size * buffer_pct)

    def _find_available_by_capacity(
        self,
        rooms: list[Room],
        student_count: int,
        day: Day,
        slot: int,
        week_type: WeekType = WeekType.BOTH,
        allow_special: bool = False,
        groups: list[str] | None = None,
    ) -> Room | None:
        """Find available room by capacity.

        Args:
            rooms: List of rooms to search
            student_count: Number of students
            day: Day of the week
            slot: Slot number
            week_type: Week type to check
            allow_special: Whether to allow special rooms
            groups: Optional list of groups to check building restrictions

        Returns:
            Suitable Room or None if not found
        """
        # Filter available rooms (not occupied and not special unless allowed)
        available = [
            r
            for r in rooms
            if not self._is_room_occupied(r, day, slot, week_type)
            and (allow_special or not r.is_special)
        ]

        # Filter out reserved buildings that these groups cannot use
        if groups:
            available = [
                r
                for r in available
                if self._is_address_allowed_for_groups(r.address, groups)
            ]

        if not available:
            return None

        # Primary: exact capacity match (room.capacity >= students)
        suitable = [r for r in available if r.capacity >= student_count]
        if suitable:
            # Return smallest room that fits (minimize waste)
            return min(suitable, key=lambda r: r.capacity)

        # Fallback: add buffer to room capacity for rooms that are slightly too small
        # Example: 30 students, 18-seat room, buffer=15 -> 18+15=33 >= 30 ✓
        buffer = self._calculate_buffer(student_count)

        buffered = [r for r in available if (r.capacity + buffer) >= student_count]
        if buffered:
            # Return largest available room (closest to needed capacity)
            return max(buffered, key=lambda r: r.capacity)

        return None

    def find_room(
        self,
        stream: LectureStream,
        day: Day,
        slot: int,
        week_type: WeekType = WeekType.BOTH,
    ) -> Room | None:
        """Find a room for a stream with priority-based selection.

        Priority order:
        0. Instructor special rooms (is_special=True, highest priority)
        1. Subject-specific rooms (from subject-rooms.json)
        2. Instructor room preferences (from instructor-rooms.json)
        3. Group building preferences (from group-buildings.json)
        4. General pool - find by capacity

        Args:
            stream: LectureStream to find room for
            day: Day of the week
            slot: Slot number
            week_type: Week type to check

        Returns:
            Suitable Room or None if not found
        """
        # 0. Instructor special rooms (highest priority)
        clean_name = self._clean_instructor_name(stream.instructor)
        special_rooms = self._get_instructor_special_rooms(clean_name, "lecture")
        if special_rooms:
            room = self._find_available_by_capacity(
                special_rooms,
                stream.student_count,
                day,
                slot,
                week_type,
                allow_special=True,
            )
            if room:
                return room

        # 1. Subject-specific rooms (strict - no fallback if defined)
        if stream.subject in self.subject_rooms:
            allowed = self._get_subject_rooms(stream.subject, "lecture")
            if allowed:
                # Subject has specific rooms for lectures - must use them, no fallback
                room = self._find_available_by_capacity(
                    allowed,
                    stream.student_count,
                    day,
                    slot,
                    week_type,
                    allow_special=True,
                )
                return room  # Returns room or None, no fallback to general pool

        # 2. Instructor non-special room preferences
        if clean_name in self.instructor_rooms:
            allowed = self._get_instructor_rooms(clean_name, "lecture")
            room = self._find_available_by_capacity(
                allowed, stream.student_count, day, slot, week_type, allow_special=True
            )
            if room:
                return room

        # 3. Group building preferences
        preferred_rooms = self._get_group_building_rooms(stream.groups)
        if preferred_rooms:
            room = self._find_available_by_capacity(
                preferred_rooms,
                stream.student_count,
                day,
                slot,
                week_type,
                allow_special=False,
            )
            if room:
                return room

        # 4. General pool - find by capacity (excludes reserved buildings for other specialties)
        return self._find_available_by_capacity(
            self.rooms,
            stream.student_count,
            day,
            slot,
            week_type,
            allow_special=False,
            groups=stream.groups,
        )

    def reserve_room(
        self, room: Room, day: Day, slot: int, week_type: WeekType = WeekType.BOTH
    ) -> None:
        """Reserve a room for a time slot.

        Args:
            room: Room to reserve
            day: Day of the week
            slot: Slot number
            week_type: Week type to reserve
        """
        self.room_schedule[(day, slot, week_type)].add(room.name)

    def release_room(
        self,
        room_name: str,
        day: Day,
        slot: int,
        week_type: WeekType = WeekType.BOTH,
    ) -> None:
        """Release a previously reserved room (inverse of reserve_room()).

        Args:
            room_name: Name of the room to release
            day: Day of the week
            slot: Slot number
            week_type: Week type to release
        """
        self.room_schedule[(day, slot, week_type)].discard(room_name)

    def is_room_available(
        self, room_name: str, day: Day, slot: int, week_type: WeekType = WeekType.BOTH
    ) -> bool:
        """Check if a room is available at a given time.

        Args:
            room_name: Name of the room
            day: Day of the week
            slot: Slot number
            week_type: Week type to check

        Returns:
            True if the room is available, False otherwise
        """
        for room in self.rooms:
            if room.name == room_name:
                return not self._is_room_occupied(room, day, slot, week_type)
        return False

    def get_room_by_name(
        self, room_name: str, address: str | None = None
    ) -> Room | None:
        """Get a room by name and optionally address.

        Args:
            room_name: Name of the room
            address: Optional address to disambiguate rooms with same name

        Returns:
            Room object or None if not found
        """
        for room in self.rooms:
            if room.name == room_name:
                if address is None or room.address == address:
                    return room
        return None

    def find_room_for_practical(
        self,
        stream: PracticalStream,
        day: Day,
        slot: int,
        week_type: WeekType = WeekType.BOTH,
    ) -> Room | None:
        """Find a room for a practical stream with priority-based selection.

        Priority order:
        0. Instructor special rooms (is_special=True, highest priority)
        1. Subject-specific rooms for practicals (from subject-rooms.json)
        2. Instructor room preferences for practicals (from instructor-rooms.json)
        3. Group building preferences (from group-buildings.json)
        4. General pool - find by capacity

        Args:
            stream: PracticalStream to find room for
            day: Day of the week
            slot: Slot number
            week_type: Week type to check

        Returns:
            Suitable Room or None if not found
        """
        # 0. Instructor special rooms (highest priority)
        clean_name = self._clean_instructor_name(stream.instructor)
        special_rooms = self._get_instructor_special_rooms(clean_name, "practice")
        if special_rooms:
            room = self._find_available_by_capacity(
                special_rooms,
                stream.student_count,
                day,
                slot,
                week_type,
                allow_special=True,
            )
            if room:
                return room

        # 1. Subject-specific rooms for practicals (strict - no fallback if defined)
        if stream.subject in self.subject_rooms:
            allowed = self._get_subject_rooms(stream.subject, "practice")
            if allowed:
                # Subject has specific rooms for practicals - must use them, no fallback
                room = self._find_available_by_capacity(
                    allowed,
                    stream.student_count,
                    day,
                    slot,
                    week_type,
                    allow_special=True,
                )
                return room  # Returns room or None, no fallback to general pool

        # 2. Instructor non-special room preferences for practicals
        if clean_name in self.instructor_rooms:
            allowed = self._get_instructor_rooms(clean_name, "practice")
            room = self._find_available_by_capacity(
                allowed, stream.student_count, day, slot, week_type, allow_special=True
            )
            if room:
                return room

        # 3. Group building preferences
        preferred_rooms = self._get_group_building_rooms(stream.groups)
        if preferred_rooms:
            room = self._find_available_by_capacity(
                preferred_rooms,
                stream.student_count,
                day,
                slot,
                week_type,
                allow_special=False,
            )
            if room:
                return room

        # 4. General pool - find by capacity (excludes reserved buildings for other specialties)
        return self._find_available_by_capacity(
            self.rooms,
            stream.student_count,
            day,
            slot,
            week_type,
            allow_special=False,
            groups=stream.groups,
        )

    def find_room_for_stage3(
        self,
        stream: Stage3PracticalStream,
        day: Day,
        slot: int,
        week_type: WeekType = WeekType.BOTH,
    ) -> Room | None:
        """Find a room for a Stage 3 practical stream with priority-based selection.

        Priority order:
        0. Instructor special rooms (is_special=True, highest priority)
        1. Subject-specific rooms for practicals (from subject-rooms.json)
        2. Instructor room preferences for practicals (from instructor-rooms.json)
        3. Group building preferences (from group-buildings.json)
        4. General pool - find by capacity

        Args:
            stream: Stage3PracticalStream to find room for
            day: Day of the week
            slot: Slot number
            week_type: Week type to check

        Returns:
            Suitable Room or None if not found
        """

        # Filter out rooms at excluded addresses for this stream
        def filter_excluded(rooms: list[Room]) -> list[Room]:
            return [
                r
                for r in rooms
                if not self._is_address_excluded_for_stream(stream.id, r.address)
            ]

        # 0. Instructor special rooms (highest priority)
        clean_name = self._clean_instructor_name(stream.instructor)
        special_rooms = self._get_instructor_special_rooms(clean_name, "practice")
        if special_rooms:
            special_rooms = filter_excluded(special_rooms)
            room = self._find_available_by_capacity(
                special_rooms,
                stream.student_count,
                day,
                slot,
                week_type,
                allow_special=True,
            )
            if room:
                return room

        # 1. Subject-specific rooms for practicals (strict - no fallback if defined)
        if stream.subject in self.subject_rooms:
            allowed = self._get_subject_rooms(stream.subject, "practice")
            if allowed:
                allowed = filter_excluded(allowed)
                room = self._find_available_by_capacity(
                    allowed,
                    stream.student_count,
                    day,
                    slot,
                    week_type,
                    allow_special=True,
                )
                return room  # Returns room or None, no fallback to general pool

        # 2. Instructor non-special room preferences for practicals
        if clean_name in self.instructor_rooms:
            allowed = self._get_instructor_rooms(clean_name, "practice")
            allowed = filter_excluded(allowed)
            room = self._find_available_by_capacity(
                allowed, stream.student_count, day, slot, week_type, allow_special=True
            )
            if room:
                return room

        # 3. Group building preferences
        preferred_rooms = self._get_group_building_rooms(stream.groups)
        if preferred_rooms:
            preferred_rooms = filter_excluded(preferred_rooms)
            room = self._find_available_by_capacity(
                preferred_rooms,
                stream.student_count,
                day,
                slot,
                week_type,
                allow_special=False,
            )
            if room:
                return room

        # 4. General pool - find by capacity (excludes reserved buildings for other specialties)
        general_rooms = filter_excluded(self.rooms)
        return self._find_available_by_capacity(
            general_rooms,
            stream.student_count,
            day,
            slot,
            week_type,
            allow_special=False,
            groups=stream.groups,
        )

    def find_room_for_stage4(
        self,
        stream: Stage4LectureStream,
        day: Day,
        slot: int,
        week_type: WeekType = WeekType.BOTH,
    ) -> Room | None:
        """Find a room for a Stage 4 single-group lecture with priority-based selection.

        Priority order (same as Stage 1 lectures):
        0. Instructor special rooms (is_special=True, highest priority)
        1. Subject-specific rooms (from subject-rooms.json)
        2. Instructor room preferences (from instructor-rooms.json)
        3. Group building preferences (from group-buildings.json)
        4. General pool - find by capacity

        Args:
            stream: Stage4LectureStream to find room for
            day: Day of the week
            slot: Slot number
            week_type: Week type to check

        Returns:
            Suitable Room or None if not found
        """
        # 0. Instructor special rooms (highest priority)
        clean_name = self._clean_instructor_name(stream.instructor)
        special_rooms = self._get_instructor_special_rooms(clean_name, "lecture")
        if special_rooms:
            room = self._find_available_by_capacity(
                special_rooms,
                stream.student_count,
                day,
                slot,
                week_type,
                allow_special=True,
            )
            if room:
                return room

        # 1. Subject-specific rooms (strict - no fallback if defined)
        if stream.subject in self.subject_rooms:
            allowed = self._get_subject_rooms(stream.subject, "lecture")
            if allowed:
                # Subject has specific rooms for lectures - must use them, no fallback
                room = self._find_available_by_capacity(
                    allowed,
                    stream.student_count,
                    day,
                    slot,
                    week_type,
                    allow_special=True,
                )
                return room  # Returns room or None, no fallback to general pool

        # 2. Instructor non-special room preferences
        if clean_name in self.instructor_rooms:
            allowed = self._get_instructor_rooms(clean_name, "lecture")
            room = self._find_available_by_capacity(
                allowed, stream.student_count, day, slot, week_type, allow_special=True
            )
            if room:
                return room

        # 3. Group building preferences
        preferred_rooms = self._get_group_building_rooms(stream.groups)
        if preferred_rooms:
            room = self._find_available_by_capacity(
                preferred_rooms,
                stream.student_count,
                day,
                slot,
                week_type,
                allow_special=False,
            )
            if room:
                return room

        # 4. General pool - find by capacity (excludes reserved buildings for other specialties)
        return self._find_available_by_capacity(
            self.rooms,
            stream.student_count,
            day,
            slot,
            week_type,
            allow_special=False,
            groups=stream.groups,
        )

    def find_room_for_stage5(
        self,
        stream: Stage5PracticalStream,
        day: Day,
        slot: int,
        week_type: WeekType = WeekType.BOTH,
    ) -> Room | None:
        """Find a room for a Stage 5 single-group practical with priority-based selection.

        Priority order (same as Stage 3 practicals):
        0. Instructor special rooms (is_special=True, highest priority)
        1. Subject-specific rooms for practicals (from subject-rooms.json)
        2. Instructor room preferences for practicals (from instructor-rooms.json)
        3. Group building preferences (from group-buildings.json)
        4. General pool - find by capacity

        Args:
            stream: Stage5PracticalStream to find room for
            day: Day of the week
            slot: Slot number
            week_type: Week type to check

        Returns:
            Suitable Room or None if not found
        """

        # Filter out rooms at excluded addresses for this stream
        def filter_excluded(rooms: list[Room]) -> list[Room]:
            return [
                r
                for r in rooms
                if not self._is_address_excluded_for_stream(stream.id, r.address)
            ]

        # 0. Instructor special rooms (highest priority)
        clean_name = self._clean_instructor_name(stream.instructor)
        special_rooms = self._get_instructor_special_rooms(clean_name, "practice")
        if special_rooms:
            special_rooms = filter_excluded(special_rooms)
            room = self._find_available_by_capacity(
                special_rooms,
                stream.student_count,
                day,
                slot,
                week_type,
                allow_special=True,
            )
            if room:
                return room

        # 1. Subject-specific rooms for practicals (strict - no fallback if defined)
        if stream.subject in self.subject_rooms:
            allowed = self._get_subject_rooms(stream.subject, "practice")
            if allowed:
                allowed = filter_excluded(allowed)
                room = self._find_available_by_capacity(
                    allowed,
                    stream.student_count,
                    day,
                    slot,
                    week_type,
                    allow_special=True,
                )
                return room  # Returns room or None, no fallback to general pool

        # 2. Instructor non-special room preferences for practicals
        if clean_name in self.instructor_rooms:
            allowed = self._get_instructor_rooms(clean_name, "practice")
            allowed = filter_excluded(allowed)
            room = self._find_available_by_capacity(
                allowed, stream.student_count, day, slot, week_type, allow_special=True
            )
            if room:
                return room

        # 3. Group building preferences
        preferred_rooms = self._get_group_building_rooms(stream.groups)
        if preferred_rooms:
            preferred_rooms = filter_excluded(preferred_rooms)
            room = self._find_available_by_capacity(
                preferred_rooms,
                stream.student_count,
                day,
                slot,
                week_type,
                allow_special=False,
            )
            if room:
                return room

        # 4. General pool - find by capacity (excludes reserved buildings for other specialties)
        general_rooms = filter_excluded(self.rooms)
        return self._find_available_by_capacity(
            general_rooms,
            stream.student_count,
            day,
            slot,
            week_type,
            allow_special=False,
            groups=stream.groups,
        )

    def find_room_for_stage6(
        self,
        stream: Stage6LabStream,
        day: Day,
        slot: int,
        week_type: WeekType = WeekType.BOTH,
    ) -> Room | None:
        """Find a room for a Stage 6 lab stream with priority-based selection.

        Priority order (same as other stages but with 'lab' type):
        0. Instructor special rooms (is_special=True, highest priority)
        1. Subject-specific rooms for labs (from subject-rooms.json)
        2. Instructor room preferences for labs (from instructor-rooms.json)
        3. Group building preferences (from group-buildings.json)
        4. General pool - find by capacity

        Args:
            stream: Stage6LabStream to find room for
            day: Day of the week
            slot: Slot number
            week_type: Week type to check

        Returns:
            Suitable Room or None if not found
        """

        # Filter out rooms at excluded addresses for this stream
        def filter_excluded(rooms: list[Room]) -> list[Room]:
            return [
                r
                for r in rooms
                if not self._is_address_excluded_for_stream(stream.id, r.address)
            ]

        # 0. Instructor special rooms (highest priority)
        clean_name = self._clean_instructor_name(stream.instructor)
        special_rooms = self._get_instructor_special_rooms(clean_name, "lab")
        if special_rooms:
            special_rooms = filter_excluded(special_rooms)
            room = self._find_available_by_capacity(
                special_rooms,
                stream.student_count,
                day,
                slot,
                week_type,
                allow_special=True,
            )
            if room:
                return room

        # 1. Subject-specific rooms for labs (strict - no fallback if defined)
        if stream.subject in self.subject_rooms:
            allowed = self._get_subject_rooms(stream.subject, "lab")
            if allowed:
                allowed = filter_excluded(allowed)
                room = self._find_available_by_capacity(
                    allowed,
                    stream.student_count,
                    day,
                    slot,
                    week_type,
                    allow_special=True,
                )
                return room  # Returns room or None, no fallback to general pool

        # 2. Instructor non-special room preferences for labs
        if clean_name in self.instructor_rooms:
            allowed = self._get_instructor_rooms(clean_name, "lab")
            allowed = filter_excluded(allowed)
            room = self._find_available_by_capacity(
                allowed, stream.student_count, day, slot, week_type, allow_special=True
            )
            if room:
                return room

        # 3. Group building preferences
        preferred_rooms = self._get_group_building_rooms(stream.groups)
        if preferred_rooms:
            preferred_rooms = filter_excluded(preferred_rooms)
            room = self._find_available_by_capacity(
                preferred_rooms,
                stream.student_count,
                day,
                slot,
                week_type,
                allow_special=False,
            )
            if room:
                return room

        # 4. General pool - find by capacity (excludes reserved buildings for other specialties)
        general_rooms = filter_excluded(self.rooms)
        return self._find_available_by_capacity(
            general_rooms,
            stream.student_count,
            day,
            slot,
            week_type,
            allow_special=False,
            groups=stream.groups,
        )
