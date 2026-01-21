"""Conflict tracking for schedule generation."""

from collections import defaultdict

from .constants import get_slot_start_time
from .models import Day, UnscheduledReason, WeekType
from .utils import clean_instructor_name


class ConflictTracker:
    """Tracks scheduling conflicts for instructors, groups, and time slots.

    This class maintains three separate schedules to detect and prevent conflicts:
    - instructor_schedule: Tracks which instructors are busy at each (day, slot, week_type)
    - group_schedule: Tracks which groups have classes at each (day, slot, week_type)
    - group_daily_load: Counts how many lectures each group has per day for even distribution
    - group_building_schedule: Tracks which building each group is in at each (day, slot)
    - group_subject_daily_hours: Tracks hours per subject per group per day (Stage 2)
    - _weekly_unavailable: Weekly unavailability from instructor-availability.json
    - _nearby_buildings: Sets of building addresses that are considered nearby
    - _instructor_day_constraints: Day-based teaching constraints from instructor-days.json
    """

    def __init__(
        self,
        instructor_availability: list[dict] | None = None,
        nearby_buildings: dict | None = None,
        instructor_day_constraints: list[dict] | None = None,
    ) -> None:
        # (day, slot, week_type) -> set of instructors
        self.instructor_schedule: dict[tuple[Day, int, WeekType], set[str]] = (
            defaultdict(set)
        )
        # (day, slot, week_type) -> set of groups
        self.group_schedule: dict[tuple[Day, int, WeekType], set[str]] = defaultdict(
            set
        )
        # (group, day) -> count of lectures
        self.group_daily_load: dict[tuple[str, Day], int] = defaultdict(int)
        # (group, day, slot, week_type) -> building address
        self.group_building_schedule: dict[tuple[str, Day, int, WeekType], str] = {}
        # (group, day, subject) -> hours scheduled (Stage 2)
        self.group_subject_daily_hours: dict[tuple[str, Day, str], int] = defaultdict(
            int
        )
        # Build weekly unavailability lookup from instructor availability data
        self._weekly_unavailable = self._build_availability_lookup(
            instructor_availability
        )
        # Build nearby buildings lookup for building change time constraint
        self._nearby_buildings = self._build_nearby_buildings_lookup(nearby_buildings)
        # Build instructor day constraints lookup
        self._instructor_day_constraints = self._build_instructor_day_constraints(
            instructor_day_constraints
        )

    def _build_availability_lookup(
        self, availability: list[dict] | None
    ) -> dict[str, dict[str, set[str]]]:
        """Build lookup dictionary for weekly unavailability.

        Args:
            availability: List of instructor availability records from JSON

        Returns:
            Dictionary mapping normalized instructor name to {day: set(times)}
        """
        if not availability:
            return {}

        lookup: dict[str, dict[str, set[str]]] = {}
        for record in availability:
            name = record.get("name", "")
            if not name:
                continue

            weekly = record.get("weekly_unavailable", {})
            if not weekly:
                continue

            # Use the name as-is since availability file has clean names
            lookup[name] = {day: set(times) for day, times in weekly.items()}

        return lookup

    def _build_nearby_buildings_lookup(
        self, nearby_buildings: dict | None
    ) -> list[set[str]]:
        """Build list of nearby building sets from nearby-buildings.json.

        Args:
            nearby_buildings: Dictionary with "groups" key containing list of
                              {"addresses": [...]} objects

        Returns:
            List of sets, where each set contains addresses that are nearby each other
        """
        if not nearby_buildings:
            return []

        groups = nearby_buildings.get("groups", [])
        result = []
        for group in groups:
            addresses = group.get("addresses", [])
            if addresses:
                result.append(set(addresses))
        return result

    def _build_instructor_day_constraints(
        self, constraints: list[dict] | None
    ) -> dict[str, dict]:
        """Build lookup dictionary for instructor day constraints.

        Args:
            constraints: List of instructor day constraint records from JSON

        Returns:
            Dictionary mapping instructor name to constraint info:
            {
                "instructor_name": {
                    "year_days": {1: ["monday", "tuesday"], 2: ["wednesday"]},
                    "one_day_only": True/False
                }
            }
        """
        if not constraints:
            return {}

        lookup: dict[str, dict] = {}
        for record in constraints:
            name = record.get("name", "")
            if not name:
                continue

            constraint_info: dict = {}

            # Year-day constraints: instructor can only teach specific years on specific days
            year_days = record.get("year_days", {})
            if year_days:
                # Convert year keys to int and day values to lowercase
                constraint_info["year_days"] = {
                    int(year): [d.lower() for d in days]
                    for year, days in year_days.items()
                }

            # One-day-per-week constraint: all classes must be on the same day
            if record.get("one_day_only", False):
                constraint_info["one_day_only"] = True

            if constraint_info:
                lookup[name] = constraint_info

        return lookup

    def _are_buildings_nearby(self, address1: str, address2: str) -> bool:
        """Check if two building addresses are considered nearby.

        Buildings are nearby if they are in the same group in nearby-buildings.json,
        or if they are the same building.

        Args:
            address1: First building address
            address2: Second building address

        Returns:
            True if buildings are nearby (no gap required between classes)
        """
        if address1 == address2:
            return True

        for nearby_group in self._nearby_buildings:
            if address1 in nearby_group and address2 in nearby_group:
                return True

        return False

    def _is_weekly_unavailable(self, instructor: str, day: Day, slot: int) -> bool:
        """Check if instructor is unavailable at this day/time per weekly schedule.

        Args:
            instructor: Instructor name (may have prefix like "а.о.")
            day: Day of the week
            slot: Slot number

        Returns:
            True if instructor is unavailable according to weekly schedule
        """
        if not self._weekly_unavailable:
            return False

        # Clean instructor name to match availability file format
        cleaned_name = clean_instructor_name(instructor)

        # Check if instructor has availability data
        if cleaned_name not in self._weekly_unavailable:
            return False

        day_unavailable = self._weekly_unavailable[cleaned_name]
        day_name = day.value  # e.g., "monday"

        if day_name not in day_unavailable:
            return False

        # Get slot start time
        slot_time = get_slot_start_time(slot)
        if not slot_time:
            return False

        return slot_time in day_unavailable[day_name]

    def is_instructor_available(
        self, instructor: str, day: Day, slot: int, week_type: WeekType = WeekType.BOTH
    ) -> bool:
        """Check if instructor is available at the given time slot.

        Args:
            instructor: Instructor name
            day: Day of the week
            slot: Slot number
            week_type: Week type to check (ODD, EVEN, or BOTH)

        Returns:
            True if instructor is available, False if there's a conflict
        """
        # Check weekly unavailability from instructor-availability.json
        if self._is_weekly_unavailable(instructor, day, slot):
            return False

        # Clean instructor name to handle different prefixes (а.о., с.п., etc.)
        cleaned = clean_instructor_name(instructor)

        # Check exact match
        if cleaned in self.instructor_schedule[(day, slot, week_type)]:
            return False

        # If checking BOTH weeks, also check ODD and EVEN separately
        if week_type == WeekType.BOTH:
            if cleaned in self.instructor_schedule[(day, slot, WeekType.ODD)]:
                return False
            if cleaned in self.instructor_schedule[(day, slot, WeekType.EVEN)]:
                return False

        # If checking specific week, also check BOTH
        if week_type in (WeekType.ODD, WeekType.EVEN):
            if cleaned in self.instructor_schedule[(day, slot, WeekType.BOTH)]:
                return False

        return True

    def are_groups_available(
        self,
        groups: list[str],
        day: Day,
        slot: int,
        week_type: WeekType = WeekType.BOTH,
    ) -> bool:
        """Check if all groups are available at the given time slot.

        Args:
            groups: List of group names
            day: Day of the week
            slot: Slot number
            week_type: Week type to check (ODD, EVEN, or BOTH)

        Returns:
            True if all groups are available, False if any group has a conflict
        """
        for group in groups:
            # Check exact match
            if group in self.group_schedule[(day, slot, week_type)]:
                return False

            # If checking BOTH weeks, also check ODD and EVEN separately
            if week_type == WeekType.BOTH:
                if group in self.group_schedule[(day, slot, WeekType.ODD)]:
                    return False
                if group in self.group_schedule[(day, slot, WeekType.EVEN)]:
                    return False

            # If checking specific week, also check BOTH
            if week_type in (WeekType.ODD, WeekType.EVEN):
                if group in self.group_schedule[(day, slot, WeekType.BOTH)]:
                    return False

        return True

    def get_group_daily_load(self, group: str, day: Day) -> int:
        """Get the number of lectures a group has on a specific day.

        Args:
            group: Group name
            day: Day of the week

        Returns:
            Number of lectures scheduled for this group on this day
        """
        return self.group_daily_load[(group, day)]

    def get_groups_total_daily_load(self, groups: list[str], day: Day) -> int:
        """Get the total daily load for a list of groups.

        Args:
            groups: List of group names
            day: Day of the week

        Returns:
            Sum of lectures scheduled for all groups on this day
        """
        return sum(self.get_group_daily_load(group, day) for group in groups)

    def reserve(
        self,
        instructor: str,
        groups: list[str],
        day: Day,
        slot: int,
        week_type: WeekType = WeekType.BOTH,
        building_address: str | None = None,
    ) -> None:
        """Reserve a time slot for an instructor and groups.

        Args:
            instructor: Instructor name
            groups: List of group names
            day: Day of the week
            slot: Slot number
            week_type: Week type to reserve (ODD, EVEN, or BOTH)
            building_address: Building address for building change time constraint
        """
        # Clean instructor name to handle different prefixes (а.о., с.п., etc.)
        cleaned = clean_instructor_name(instructor)
        self.instructor_schedule[(day, slot, week_type)].add(cleaned)

        for group in groups:
            self.group_schedule[(day, slot, week_type)].add(group)

        # Increment daily load for each group
        for group in groups:
            self.group_daily_load[(group, day)] += 1

        # Track building address for building change time constraint
        if building_address:
            for group in groups:
                self.group_building_schedule[(group, day, slot, week_type)] = (
                    building_address
                )

    def get_group_building_at_slot(
        self, group: str, day: Day, slot: int, week_type: WeekType = WeekType.BOTH
    ) -> str | None:
        """Get the building address where a group has a class at a specific slot.

        Args:
            group: Group name
            day: Day of the week
            slot: Slot number
            week_type: Week type to check

        Returns:
            Building address if group has a class at this slot, None otherwise
        """
        # Check exact match
        if (group, day, slot, week_type) in self.group_building_schedule:
            return self.group_building_schedule[(group, day, slot, week_type)]

        # If checking BOTH weeks, also check ODD and EVEN
        if week_type == WeekType.BOTH:
            if (group, day, slot, WeekType.ODD) in self.group_building_schedule:
                return self.group_building_schedule[(group, day, slot, WeekType.ODD)]
            if (group, day, slot, WeekType.EVEN) in self.group_building_schedule:
                return self.group_building_schedule[(group, day, slot, WeekType.EVEN)]

        # If checking specific week, also check BOTH
        if week_type in (WeekType.ODD, WeekType.EVEN):
            if (group, day, slot, WeekType.BOTH) in self.group_building_schedule:
                return self.group_building_schedule[(group, day, slot, WeekType.BOTH)]

        return None

    def check_building_gap_constraint(
        self,
        groups: list[str],
        day: Day,
        slot: int,
        building_address: str,
        week_type: WeekType = WeekType.BOTH,
    ) -> tuple[bool, str | None, str]:
        """Check if scheduling at this slot would violate building change time constraint.

        The constraint: When consecutive classes are in different (non-nearby) buildings,
        there must be a 1-slot gap for travel time.

        Args:
            groups: List of group names
            day: Day of the week
            slot: Slot number
            building_address: Building address for the proposed class
            week_type: Week type to check

        Returns:
            Tuple of (is_valid, conflicting_group, details)
            - is_valid: True if no building gap violation
            - conflicting_group: Group name that has the conflict, None if valid
            - details: Human-readable description of the conflict
        """
        if not building_address:
            return (True, None, "")

        for group in groups:
            # Check adjacent slots (slot-1 and slot+1)
            for adjacent_slot in [slot - 1, slot + 1]:
                if adjacent_slot < 1:
                    continue

                adjacent_building = self.get_group_building_at_slot(
                    group, day, adjacent_slot, week_type
                )

                if adjacent_building and not self._are_buildings_nearby(
                    building_address, adjacent_building
                ):
                    direction = "previous" if adjacent_slot < slot else "next"
                    return (
                        False,
                        group,
                        f"Group '{group}' has class at {direction} slot ({adjacent_slot}) "
                        f"in '{adjacent_building}' which is not nearby '{building_address}'. "
                        f"A gap slot is required for building change.",
                    )

        return (True, None, "")

    def is_slot_available(
        self,
        instructor: str,
        groups: list[str],
        day: Day,
        slot: int,
        week_type: WeekType = WeekType.BOTH,
    ) -> bool:
        """Check if a slot is available for the given instructor and groups.

        Args:
            instructor: Instructor name
            groups: List of group names
            day: Day of the week
            slot: Slot number
            week_type: Week type to check (ODD, EVEN, or BOTH)

        Returns:
            True if the slot is available for both instructor and all groups
        """
        return self.is_instructor_available(
            instructor, day, slot, week_type
        ) and self.are_groups_available(groups, day, slot, week_type)

    def are_consecutive_slots_available(
        self,
        instructor: str,
        groups: list[str],
        day: Day,
        start_slot: int,
        num_slots: int,
        week_type: WeekType = WeekType.BOTH,
    ) -> bool:
        """Check if consecutive slots are available.

        Args:
            instructor: Instructor name
            groups: List of group names
            day: Day of the week
            start_slot: Starting slot number
            num_slots: Number of consecutive slots needed
            week_type: Week type to check (ODD, EVEN, or BOTH)

        Returns:
            True if all consecutive slots are available
        """
        for i in range(num_slots):
            if not self.is_slot_available(
                instructor, groups, day, start_slot + i, week_type
            ):
                return False
        return True

    def check_slot_availability_reason(
        self,
        instructor: str,
        groups: list[str],
        day: Day,
        slot: int,
        week_type: WeekType = WeekType.BOTH,
    ) -> tuple[bool, UnscheduledReason | None, str]:
        """Check slot availability and return specific failure reason.

        Args:
            instructor: Instructor name
            groups: List of group names
            day: Day of the week
            slot: Slot number
            week_type: Week type to check (ODD, EVEN, or BOTH)

        Returns:
            Tuple of (is_available, reason, details)
            - is_available: True if slot is available
            - reason: UnscheduledReason if not available, None if available
            - details: Human-readable description of the conflict
        """
        # Check weekly unavailability from instructor-availability.json
        if self._is_weekly_unavailable(instructor, day, slot):
            return (
                False,
                UnscheduledReason.INSTRUCTOR_UNAVAILABLE,
                f"Instructor '{instructor}' is unavailable on {day.value} slot {slot} "
                f"per weekly availability schedule",
            )

        # Check instructor conflict
        if not self.is_instructor_available(instructor, day, slot, week_type):
            return (
                False,
                UnscheduledReason.INSTRUCTOR_CONFLICT,
                f"Instructor '{instructor}' already scheduled on {day.value} slot {slot}",
            )

        # Check group conflicts
        for group in groups:
            # Check exact match
            if group in self.group_schedule[(day, slot, week_type)]:
                return (
                    False,
                    UnscheduledReason.GROUP_CONFLICT,
                    f"Group '{group}' already scheduled on {day.value} slot {slot}",
                )

            # If checking BOTH weeks, also check ODD and EVEN separately
            if week_type == WeekType.BOTH:
                if group in self.group_schedule[(day, slot, WeekType.ODD)]:
                    return (
                        False,
                        UnscheduledReason.GROUP_CONFLICT,
                        f"Group '{group}' already scheduled on {day.value} slot {slot} "
                        f"(odd week)",
                    )
                if group in self.group_schedule[(day, slot, WeekType.EVEN)]:
                    return (
                        False,
                        UnscheduledReason.GROUP_CONFLICT,
                        f"Group '{group}' already scheduled on {day.value} slot {slot} "
                        f"(even week)",
                    )

            # If checking specific week, also check BOTH
            if week_type in (WeekType.ODD, WeekType.EVEN):
                if group in self.group_schedule[(day, slot, WeekType.BOTH)]:
                    return (
                        False,
                        UnscheduledReason.GROUP_CONFLICT,
                        f"Group '{group}' already scheduled on {day.value} slot {slot} "
                        f"(both weeks)",
                    )

        return (True, None, "")

    def check_consecutive_slots_reason(
        self,
        instructor: str,
        groups: list[str],
        day: Day,
        start_slot: int,
        num_slots: int,
        week_type: WeekType = WeekType.BOTH,
    ) -> tuple[bool, UnscheduledReason | None, str]:
        """Check consecutive slots availability and return specific failure reason.

        Args:
            instructor: Instructor name
            groups: List of group names
            day: Day of the week
            start_slot: Starting slot number
            num_slots: Number of consecutive slots needed
            week_type: Week type to check (ODD, EVEN, or BOTH)

        Returns:
            Tuple of (is_available, reason, details)
        """
        for i in range(num_slots):
            slot = start_slot + i
            is_available, reason, details = self.check_slot_availability_reason(
                instructor, groups, day, slot, week_type
            )
            if not is_available:
                return (
                    False,
                    reason,
                    f"Slot {i + 1}/{num_slots}: {details}",
                )
        return (True, None, "")

    # ========================
    # Stage 2 specific methods
    # ========================

    def get_group_subject_daily_hours(self, group: str, day: Day, subject: str) -> int:
        """Get hours a group has for a subject on a specific day.

        Args:
            group: Group name
            day: Day of the week
            subject: Subject name

        Returns:
            Number of hours scheduled for this subject
        """
        return self.group_subject_daily_hours[(group, day, subject)]

    def can_add_subject_hours(
        self, groups: list[str], day: Day, subject: str, hours_to_add: int
    ) -> tuple[bool, bool]:
        """Check if hours can be added for a subject without exceeding daily limit.

        The 2-hour rule: No more than 2 hours per subject per day per group (normal).
        Extreme case: 3 hours allowed only when no other option exists.

        Args:
            groups: List of group names
            day: Day of the week
            subject: Subject name
            hours_to_add: Hours to add

        Returns:
            Tuple of (can_add_normal, can_add_extreme):
            - can_add_normal: True if ≤ 2 hours total
            - can_add_extreme: True if ≤ 3 hours total (extreme case)
        """
        for group in groups:
            current = self.group_subject_daily_hours[(group, day, subject)]
            total = current + hours_to_add

            if total > 3:
                return (False, False)
            if total > 2:
                return (False, True)

        return (True, True)

    def reserve_subject_hours(
        self,
        groups: list[str],
        day: Day,
        subject: str,
        hours: int,
    ) -> None:
        """Reserve subject hours for groups on a day.

        Args:
            groups: List of group names
            day: Day of the week
            subject: Subject name
            hours: Number of hours to reserve
        """
        for group in groups:
            self.group_subject_daily_hours[(group, day, subject)] += hours

    def get_group_slots_on_day(
        self, group: str, day: Day, week_type: WeekType = WeekType.BOTH
    ) -> list[int]:
        """Get list of slots where a group has classes on a day.

        Args:
            group: Group name
            day: Day of the week
            week_type: Week type to check

        Returns:
            Sorted list of slot numbers
        """
        slots = set()

        # Check all possible slots (1-13)
        for slot in range(1, 14):
            # Check exact week type
            if group in self.group_schedule[(day, slot, week_type)]:
                slots.add(slot)

            # If checking BOTH, also check ODD and EVEN
            if week_type == WeekType.BOTH:
                if group in self.group_schedule[(day, slot, WeekType.ODD)]:
                    slots.add(slot)
                if group in self.group_schedule[(day, slot, WeekType.EVEN)]:
                    slots.add(slot)

            # If checking specific week, also check BOTH
            if week_type in (WeekType.ODD, WeekType.EVEN):
                if group in self.group_schedule[(day, slot, WeekType.BOTH)]:
                    slots.add(slot)

        return sorted(slots)

    def count_windows(self, slots: list[int]) -> int:
        """Count the number of windows (gaps) in a list of slots.

        A window is an empty slot between scheduled classes.

        Args:
            slots: Sorted list of slot numbers

        Returns:
            Number of windows
        """
        if len(slots) < 2:
            return 0

        windows = 0
        for i in range(len(slots) - 1):
            gap = slots[i + 1] - slots[i]
            if gap > 1:
                windows += gap - 1
        return windows

    def would_create_second_window(
        self,
        groups: list[str],
        day: Day,
        slot: int,
        week_type: WeekType = WeekType.BOTH,
        max_windows: int = 3,
    ) -> tuple[bool, str | None]:
        """Check if adding a class would exceed max allowed windows for any group.

        Windows (gaps) are allowed during early scheduling stages and will be
        filled in later stages. Default max is 3 windows per day.

        Args:
            groups: List of group names
            day: Day of the week
            slot: Proposed slot for the new class
            week_type: Week type to check
            max_windows: Maximum allowed windows per day (default 3)

        Returns:
            Tuple of (would_exceed_max_windows, conflicting_group)
        """
        for group in groups:
            existing_slots = self.get_group_slots_on_day(group, day, week_type)

            # If group has no existing classes, no window issue
            if not existing_slots:
                continue

            # Simulate adding the new slot
            new_slots = sorted(existing_slots + [slot])

            # Count windows after adding
            new_windows = self.count_windows(new_slots)

            if new_windows > max_windows:
                return (True, group)

        return (False, None)

    def is_building_gap_slot(
        self,
        groups: list[str],
        day: Day,
        slot: int,
        week_type: WeekType = WeekType.BOTH,
    ) -> tuple[bool, str | None]:
        """Check if a slot must be kept free for building travel.

        A slot is a building gap slot if adjacent scheduled classes are in
        different (non-nearby) buildings.

        Args:
            groups: List of group names
            day: Day of the week
            slot: Slot to check
            week_type: Week type to check

        Returns:
            Tuple of (is_gap_slot, conflicting_group)
        """
        for group in groups:
            prev_building = self.get_group_building_at_slot(
                group, day, slot - 1, week_type
            )
            next_building = self.get_group_building_at_slot(
                group, day, slot + 1, week_type
            )

            # If both adjacent slots have classes in different non-nearby buildings,
            # this slot must be a travel gap
            if prev_building and next_building:
                if not self._are_buildings_nearby(prev_building, next_building):
                    return (True, group)

        return (False, None)

    def would_exceed_daily_load(
        self,
        groups: list[str],
        day: Day,
        hours_to_add: int,
        max_load: int = 6,
        week_type: WeekType = WeekType.BOTH,
    ) -> tuple[bool, str | None]:
        """Check if adding hours would exceed daily load limit for any group.

        Args:
            groups: List of group names
            day: Day of the week
            hours_to_add: Number of hours to add
            max_load: Maximum allowed lessons per day (default 6)
            week_type: Week type to check

        Returns:
            Tuple of (would_exceed, conflicting_group)
        """
        for group in groups:
            current_load = self.get_group_daily_load(group, day)
            if current_load + hours_to_add > max_load:
                return (True, group)

        return (False, None)

    def check_instructor_day_constraint(
        self,
        instructor: str,
        day: Day,
        groups: list[str],
    ) -> tuple[bool, str]:
        """Check if instructor can teach on this day for these groups.

        Args:
            instructor: Instructor name
            day: Day of the week
            groups: List of group names (used to determine year)

        Returns:
            Tuple of (is_valid, details)
        """
        from .utils import clean_instructor_name, parse_group_year

        cleaned_name = clean_instructor_name(instructor)

        # Check if instructor has day constraints
        if cleaned_name not in self._instructor_day_constraints:
            return (True, "")

        constraints = self._instructor_day_constraints[cleaned_name]

        # Check year-day constraints
        if "year_days" in constraints:
            year_days = constraints["year_days"]
            # Determine year from first group
            if groups:
                year = parse_group_year(groups[0])
                if year in year_days:
                    allowed_days = year_days[year]
                    if day.value not in allowed_days:
                        return (
                            False,
                            f"Instructor '{instructor}' can only teach year {year} on "
                            f"{', '.join(allowed_days)}, not {day.value}",
                        )

        # Check one-day-only constraint
        if constraints.get("one_day_only", False):
            # Find the day this instructor is already teaching
            existing_days = set()
            for (d, _, _), instructors in self.instructor_schedule.items():
                if cleaned_name in instructors:
                    existing_days.add(d)

            if existing_days and day not in existing_days:
                existing_day = next(iter(existing_days))
                return (
                    False,
                    f"Instructor '{instructor}' has one-day-only constraint and is "
                    f"already scheduled on {existing_day.value}",
                )

        return (True, "")

    def load_stage1_assignments(self, assignments: list[dict]) -> None:
        """Load Stage 1 assignments into the conflict tracker.

        Args:
            assignments: List of assignment dictionaries from Stage 1 schedule JSON
        """
        for assignment in assignments:
            day_str = assignment.get("day", "")
            day = Day(day_str)
            slot = assignment.get("slot", 0)
            instructor = assignment.get("instructor", "")
            groups = assignment.get("groups", [])
            room_address = assignment.get("room_address", "")
            week_type_str = assignment.get("week_type", "both")
            week_type = WeekType(week_type_str)
            subject = assignment.get("subject", "")

            # Reserve the slot
            self.reserve(
                instructor,
                groups,
                day,
                slot,
                week_type,
                building_address=room_address,
            )

            # Also track subject hours (for 2-hour rule)
            self.reserve_subject_hours(groups, day, subject, 1)
