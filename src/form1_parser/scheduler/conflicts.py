"""Conflict tracking for schedule generation."""

from collections import defaultdict

from .constants import get_slot_start_time
from .models import Day, WeekType
from .utils import clean_instructor_name


class ConflictTracker:
    """Tracks scheduling conflicts for instructors, groups, and time slots.

    This class maintains three separate schedules to detect and prevent conflicts:
    - instructor_schedule: Tracks which instructors are busy at each (day, slot, week_type)
    - group_schedule: Tracks which groups have classes at each (day, slot, week_type)
    - group_daily_load: Counts how many lectures each group has per day for even distribution
    - _weekly_unavailable: Weekly unavailability from instructor-availability.json
    """

    def __init__(self, instructor_availability: list[dict] | None = None) -> None:
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
        # Build weekly unavailability lookup from instructor availability data
        self._weekly_unavailable = self._build_availability_lookup(
            instructor_availability
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

        # Check exact match
        if instructor in self.instructor_schedule[(day, slot, week_type)]:
            return False

        # If checking BOTH weeks, also check ODD and EVEN separately
        if week_type == WeekType.BOTH:
            if instructor in self.instructor_schedule[(day, slot, WeekType.ODD)]:
                return False
            if instructor in self.instructor_schedule[(day, slot, WeekType.EVEN)]:
                return False

        # If checking specific week, also check BOTH
        if week_type in (WeekType.ODD, WeekType.EVEN):
            if instructor in self.instructor_schedule[(day, slot, WeekType.BOTH)]:
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
    ) -> None:
        """Reserve a time slot for an instructor and groups.

        Args:
            instructor: Instructor name
            groups: List of group names
            day: Day of the week
            slot: Slot number
            week_type: Week type to reserve (ODD, EVEN, or BOTH)
        """
        self.instructor_schedule[(day, slot, week_type)].add(instructor)

        for group in groups:
            self.group_schedule[(day, slot, week_type)].add(group)

        # Increment daily load for each group
        for group in groups:
            self.group_daily_load[(group, day)] += 1

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
