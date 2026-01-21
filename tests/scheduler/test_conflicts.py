"""Tests for ConflictTracker class."""

import pytest

from form1_parser.scheduler.conflicts import ConflictTracker
from form1_parser.scheduler.models import Day, UnscheduledReason, WeekType


class TestConflictTracker:
    """Tests for ConflictTracker class."""

    def test_instructor_initially_available(self):
        tracker = ConflictTracker()
        assert tracker.is_instructor_available("Instructor1", Day.MONDAY, 1)

    def test_instructor_unavailable_after_reservation(self):
        tracker = ConflictTracker()
        tracker.reserve("Instructor1", ["Group1"], Day.MONDAY, 1)
        assert not tracker.is_instructor_available("Instructor1", Day.MONDAY, 1)

    def test_groups_initially_available(self):
        tracker = ConflictTracker()
        assert tracker.are_groups_available(["Group1", "Group2"], Day.MONDAY, 1)

    def test_groups_unavailable_after_reservation(self):
        tracker = ConflictTracker()
        tracker.reserve("Instructor1", ["Group1", "Group2"], Day.MONDAY, 1)
        assert not tracker.are_groups_available(["Group1"], Day.MONDAY, 1)
        assert not tracker.are_groups_available(["Group2"], Day.MONDAY, 1)

    def test_partial_group_conflict(self):
        tracker = ConflictTracker()
        tracker.reserve("Instructor1", ["Group1"], Day.MONDAY, 1)
        # Group1 is busy, but Group2 is not in the set - so the check should fail
        assert not tracker.are_groups_available(["Group1", "Group2"], Day.MONDAY, 1)

    def test_different_day_no_conflict(self):
        tracker = ConflictTracker()
        tracker.reserve("Instructor1", ["Group1"], Day.MONDAY, 1)
        assert tracker.is_instructor_available("Instructor1", Day.TUESDAY, 1)
        assert tracker.are_groups_available(["Group1"], Day.TUESDAY, 1)

    def test_different_slot_no_conflict(self):
        tracker = ConflictTracker()
        tracker.reserve("Instructor1", ["Group1"], Day.MONDAY, 1)
        assert tracker.is_instructor_available("Instructor1", Day.MONDAY, 2)
        assert tracker.are_groups_available(["Group1"], Day.MONDAY, 2)

    def test_group_daily_load(self):
        tracker = ConflictTracker()
        assert tracker.get_group_daily_load("Group1", Day.MONDAY) == 0
        tracker.reserve("Instructor1", ["Group1"], Day.MONDAY, 1)
        assert tracker.get_group_daily_load("Group1", Day.MONDAY) == 1
        tracker.reserve("Instructor2", ["Group1"], Day.MONDAY, 2)
        assert tracker.get_group_daily_load("Group1", Day.MONDAY) == 2

    def test_groups_total_daily_load(self):
        tracker = ConflictTracker()
        tracker.reserve("Instructor1", ["Group1", "Group2"], Day.MONDAY, 1)
        # Both groups should have 1 lecture each
        assert tracker.get_groups_total_daily_load(["Group1", "Group2"], Day.MONDAY) == 2

    def test_is_slot_available(self):
        tracker = ConflictTracker()
        assert tracker.is_slot_available("Instructor1", ["Group1"], Day.MONDAY, 1)
        tracker.reserve("Instructor1", ["Group1"], Day.MONDAY, 1)
        assert not tracker.is_slot_available("Instructor1", ["Group1"], Day.MONDAY, 1)
        # Different instructor, same group - should fail
        assert not tracker.is_slot_available("Instructor2", ["Group1"], Day.MONDAY, 1)
        # Same instructor, different group - should fail
        assert not tracker.is_slot_available("Instructor1", ["Group2"], Day.MONDAY, 1)
        # Different instructor, different group - should pass
        assert tracker.is_slot_available("Instructor2", ["Group2"], Day.MONDAY, 1)

    def test_consecutive_slots_available(self):
        tracker = ConflictTracker()
        # Check 2 consecutive slots
        assert tracker.are_consecutive_slots_available(
            "Instructor1", ["Group1"], Day.MONDAY, 1, 2
        )
        # Reserve first slot
        tracker.reserve("Instructor1", ["Group1"], Day.MONDAY, 1)
        # Now consecutive check should fail
        assert not tracker.are_consecutive_slots_available(
            "Instructor1", ["Group1"], Day.MONDAY, 1, 2
        )
        # But starting from slot 2 should work
        assert tracker.are_consecutive_slots_available(
            "Instructor1", ["Group1"], Day.MONDAY, 2, 2
        )


class TestConflictTrackerWeekTypes:
    """Tests for ConflictTracker week type handling."""

    def test_both_week_reservation_blocks_odd_and_even(self):
        tracker = ConflictTracker()
        tracker.reserve("Instructor1", ["Group1"], Day.MONDAY, 1, WeekType.BOTH)

        # Should be unavailable for ODD, EVEN, and BOTH
        assert not tracker.is_instructor_available(
            "Instructor1", Day.MONDAY, 1, WeekType.ODD
        )
        assert not tracker.is_instructor_available(
            "Instructor1", Day.MONDAY, 1, WeekType.EVEN
        )
        assert not tracker.is_instructor_available(
            "Instructor1", Day.MONDAY, 1, WeekType.BOTH
        )

    def test_odd_week_reservation_blocks_both(self):
        tracker = ConflictTracker()
        tracker.reserve("Instructor1", ["Group1"], Day.MONDAY, 1, WeekType.ODD)

        # Should be unavailable for ODD and BOTH, but available for EVEN
        assert not tracker.is_instructor_available(
            "Instructor1", Day.MONDAY, 1, WeekType.ODD
        )
        assert not tracker.is_instructor_available(
            "Instructor1", Day.MONDAY, 1, WeekType.BOTH
        )
        assert tracker.is_instructor_available(
            "Instructor1", Day.MONDAY, 1, WeekType.EVEN
        )

    def test_even_week_reservation_blocks_both(self):
        tracker = ConflictTracker()
        tracker.reserve("Instructor1", ["Group1"], Day.MONDAY, 1, WeekType.EVEN)

        # Should be unavailable for EVEN and BOTH, but available for ODD
        assert not tracker.is_instructor_available(
            "Instructor1", Day.MONDAY, 1, WeekType.EVEN
        )
        assert not tracker.is_instructor_available(
            "Instructor1", Day.MONDAY, 1, WeekType.BOTH
        )
        assert tracker.is_instructor_available(
            "Instructor1", Day.MONDAY, 1, WeekType.ODD
        )


class TestInstructorWeeklyAvailability:
    """Tests for instructor weekly availability checking."""

    def test_instructor_available_no_availability_data(self):
        """Without availability data, all instructors are available."""
        tracker = ConflictTracker()
        assert tracker.is_instructor_available("Чурикова Л.А.", Day.FRIDAY, 1)

    def test_instructor_available_with_empty_availability(self):
        """With empty availability list, all instructors are available."""
        tracker = ConflictTracker(instructor_availability=[])
        assert tracker.is_instructor_available("Чурикова Л.А.", Day.FRIDAY, 1)

    def test_instructor_weekly_unavailable(self):
        """Instructor is blocked when unavailable per weekly schedule."""
        availability = [
            {
                "name": "Чурикова Л.А.",
                "weekly_unavailable": {
                    "friday": ["09:00", "10:00", "11:00"],
                },
            }
        ]
        tracker = ConflictTracker(instructor_availability=availability)

        # Slot 1 is 09:00 - should be unavailable on Friday
        assert not tracker.is_instructor_available("Чурикова Л.А.", Day.FRIDAY, 1)
        # Slot 2 is 10:00 - should be unavailable on Friday
        assert not tracker.is_instructor_available("Чурикова Л.А.", Day.FRIDAY, 2)
        # Slot 3 is 11:00 - should be unavailable on Friday
        assert not tracker.is_instructor_available("Чурикова Л.А.", Day.FRIDAY, 3)

    def test_instructor_weekly_available(self):
        """Instructor is available when not in unavailable times."""
        availability = [
            {
                "name": "Чурикова Л.А.",
                "weekly_unavailable": {
                    "friday": ["09:00", "10:00"],
                },
            }
        ]
        tracker = ConflictTracker(instructor_availability=availability)

        # Available on different day
        assert tracker.is_instructor_available("Чурикова Л.А.", Day.MONDAY, 1)
        # Available at different time on Friday (slot 4 is 12:00)
        assert tracker.is_instructor_available("Чурикова Л.А.", Day.FRIDAY, 4)
        # Available on Tuesday
        assert tracker.is_instructor_available("Чурикова Л.А.", Day.TUESDAY, 1)

    def test_instructor_name_normalization(self):
        """Instructor names with prefixes are normalized for lookup."""
        availability = [
            {
                "name": "Чурикова Л.А.",  # Clean name in availability
                "weekly_unavailable": {
                    "friday": ["09:00"],
                },
            }
        ]
        tracker = ConflictTracker(instructor_availability=availability)

        # Stream has prefixed name "а.о.Чурикова Л.А." - should still match
        assert not tracker.is_instructor_available("а.о.Чурикова Л.А.", Day.FRIDAY, 1)
        # Other prefixes should also be normalized
        assert not tracker.is_instructor_available("с.п.Чурикова Л.А.", Day.FRIDAY, 1)
        assert not tracker.is_instructor_available("доцент Чурикова Л.А.", Day.FRIDAY, 1)

    def test_instructor_not_in_availability_data(self):
        """Instructor not in availability data is available everywhere."""
        availability = [
            {
                "name": "Чурикова Л.А.",
                "weekly_unavailable": {
                    "friday": ["09:00"],
                },
            }
        ]
        tracker = ConflictTracker(instructor_availability=availability)

        # Different instructor not in availability data - should be available
        assert tracker.is_instructor_available("Иванов И.И.", Day.FRIDAY, 1)

    def test_combined_weekly_and_reservation_conflict(self):
        """Both weekly unavailability and reservations are checked."""
        availability = [
            {
                "name": "Чурикова Л.А.",
                "weekly_unavailable": {
                    "friday": ["09:00"],
                },
            }
        ]
        tracker = ConflictTracker(instructor_availability=availability)

        # Reserve on Monday
        tracker.reserve("Чурикова Л.А.", ["Group1"], Day.MONDAY, 1)

        # Unavailable due to reservation
        assert not tracker.is_instructor_available("Чурикова Л.А.", Day.MONDAY, 1)
        # Unavailable due to weekly schedule
        assert not tracker.is_instructor_available("Чурикова Л.А.", Day.FRIDAY, 1)
        # Available - neither reserved nor in weekly unavailable
        assert tracker.is_instructor_available("Чурикова Л.А.", Day.TUESDAY, 1)

    def test_multiple_instructors_availability(self):
        """Multiple instructors with different availability schedules."""
        availability = [
            {
                "name": "Чурикова Л.А.",
                "weekly_unavailable": {"friday": ["09:00"]},
            },
            {
                "name": "Биниязов А.М.",
                "weekly_unavailable": {"monday": ["09:00", "10:00"]},
            },
        ]
        tracker = ConflictTracker(instructor_availability=availability)

        # Чурикова unavailable Friday slot 1
        assert not tracker.is_instructor_available("Чурикова Л.А.", Day.FRIDAY, 1)
        # Чурикова available Monday slot 1
        assert tracker.is_instructor_available("Чурикова Л.А.", Day.MONDAY, 1)

        # Биниязов unavailable Monday slots 1 and 2
        assert not tracker.is_instructor_available("Биниязов А.М.", Day.MONDAY, 1)
        assert not tracker.is_instructor_available("Биниязов А.М.", Day.MONDAY, 2)
        # Биниязов available Friday slot 1
        assert tracker.is_instructor_available("Биниязов А.М.", Day.FRIDAY, 1)


class TestSlotAvailabilityReason:
    """Tests for check_slot_availability_reason method."""

    def test_returns_available_when_no_conflicts(self):
        tracker = ConflictTracker()
        is_available, reason, details = tracker.check_slot_availability_reason(
            "Instructor1", ["Group1"], Day.MONDAY, 1
        )
        assert is_available is True
        assert reason is None
        assert details == ""

    def test_returns_instructor_conflict_reason(self):
        tracker = ConflictTracker()
        tracker.reserve("Instructor1", ["Group2"], Day.MONDAY, 1)

        is_available, reason, details = tracker.check_slot_availability_reason(
            "Instructor1", ["Group1"], Day.MONDAY, 1
        )

        assert is_available is False
        assert reason == UnscheduledReason.INSTRUCTOR_CONFLICT
        assert "Instructor1" in details

    def test_returns_group_conflict_reason(self):
        tracker = ConflictTracker()
        tracker.reserve("Instructor2", ["Group1"], Day.MONDAY, 1)

        is_available, reason, details = tracker.check_slot_availability_reason(
            "Instructor1", ["Group1"], Day.MONDAY, 1
        )

        assert is_available is False
        assert reason == UnscheduledReason.GROUP_CONFLICT
        assert "Group1" in details

    def test_returns_instructor_unavailable_reason(self):
        availability = [
            {
                "name": "Instructor1",
                "weekly_unavailable": {"monday": ["09:00"]},
            }
        ]
        tracker = ConflictTracker(instructor_availability=availability)

        is_available, reason, details = tracker.check_slot_availability_reason(
            "Instructor1", ["Group1"], Day.MONDAY, 1
        )

        assert is_available is False
        assert reason == UnscheduledReason.INSTRUCTOR_UNAVAILABLE
        assert "Instructor1" in details

    def test_instructor_conflict_detected_before_group(self):
        """Instructor conflict should be detected before group conflict."""
        tracker = ConflictTracker()
        # Reserve with same instructor and same group
        tracker.reserve("Instructor1", ["Group1"], Day.MONDAY, 1)

        is_available, reason, details = tracker.check_slot_availability_reason(
            "Instructor1", ["Group1"], Day.MONDAY, 1
        )

        assert is_available is False
        # Should return instructor conflict, not group conflict
        assert reason == UnscheduledReason.INSTRUCTOR_CONFLICT


class TestConsecutiveSlotsReason:
    """Tests for check_consecutive_slots_reason method."""

    def test_returns_available_when_all_slots_free(self):
        tracker = ConflictTracker()
        is_available, reason, details = tracker.check_consecutive_slots_reason(
            "Instructor1", ["Group1"], Day.MONDAY, 1, 2
        )

        assert is_available is True
        assert reason is None
        assert details == ""

    def test_returns_conflict_for_first_slot(self):
        tracker = ConflictTracker()
        tracker.reserve("Instructor1", ["Group2"], Day.MONDAY, 1)

        is_available, reason, details = tracker.check_consecutive_slots_reason(
            "Instructor1", ["Group1"], Day.MONDAY, 1, 2
        )

        assert is_available is False
        assert reason == UnscheduledReason.INSTRUCTOR_CONFLICT
        assert "Slot 1/2" in details

    def test_returns_conflict_for_second_slot(self):
        tracker = ConflictTracker()
        tracker.reserve("Instructor1", ["Group2"], Day.MONDAY, 2)  # Second slot

        is_available, reason, details = tracker.check_consecutive_slots_reason(
            "Instructor1", ["Group1"], Day.MONDAY, 1, 2
        )

        assert is_available is False
        assert reason == UnscheduledReason.INSTRUCTOR_CONFLICT
        assert "Slot 2/2" in details

    def test_returns_group_conflict_for_consecutive_slot(self):
        tracker = ConflictTracker()
        tracker.reserve("Instructor2", ["Group1"], Day.MONDAY, 2)  # Second slot has group

        is_available, reason, details = tracker.check_consecutive_slots_reason(
            "Instructor1", ["Group1"], Day.MONDAY, 1, 2
        )

        assert is_available is False
        assert reason == UnscheduledReason.GROUP_CONFLICT
        assert "Slot 2/2" in details
        assert "Group1" in details


class TestBuildingGapConstraint:
    """Tests for building change time constraint (C-7.3)."""

    @pytest.fixture
    def nearby_buildings(self):
        """Sample nearby buildings configuration."""
        return {
            "groups": [
                {"addresses": ["Building A", "Building B"]},
                {"addresses": ["Building C", "Building D"]},
            ]
        }

    def test_same_building_no_gap_required(self, nearby_buildings):
        """Test that same building doesn't require a gap."""
        tracker = ConflictTracker(nearby_buildings=nearby_buildings)

        # Reserve slot 1 in Building A
        tracker.reserve("Instructor", ["Group-11"], Day.MONDAY, 1, WeekType.BOTH, "Building A")

        # Check if slot 2 in Building A is allowed (should be OK)
        is_valid, _, _ = tracker.check_building_gap_constraint(
            ["Group-11"], Day.MONDAY, 2, "Building A", WeekType.BOTH
        )
        assert is_valid is True

    def test_nearby_buildings_no_gap_required(self, nearby_buildings):
        """Test that nearby buildings don't require a gap."""
        tracker = ConflictTracker(nearby_buildings=nearby_buildings)

        # Reserve slot 1 in Building A
        tracker.reserve("Instructor", ["Group-11"], Day.MONDAY, 1, WeekType.BOTH, "Building A")

        # Check if slot 2 in Building B (nearby) is allowed (should be OK)
        is_valid, _, _ = tracker.check_building_gap_constraint(
            ["Group-11"], Day.MONDAY, 2, "Building B", WeekType.BOTH
        )
        assert is_valid is True

    def test_different_buildings_require_gap(self, nearby_buildings):
        """Test that non-nearby buildings require a gap slot."""
        tracker = ConflictTracker(nearby_buildings=nearby_buildings)

        # Reserve slot 1 in Building A
        tracker.reserve("Instructor", ["Group-11"], Day.MONDAY, 1, WeekType.BOTH, "Building A")

        # Check if slot 2 in Building C (NOT nearby A) is allowed (should FAIL)
        is_valid, conflicting_group, details = tracker.check_building_gap_constraint(
            ["Group-11"], Day.MONDAY, 2, "Building C", WeekType.BOTH
        )
        assert is_valid is False
        assert conflicting_group == "Group-11"
        assert "gap" in details.lower()

    def test_gap_slot_allows_different_buildings(self, nearby_buildings):
        """Test that with a gap slot, different buildings are allowed."""
        tracker = ConflictTracker(nearby_buildings=nearby_buildings)

        # Reserve slot 1 in Building A
        tracker.reserve("Instructor", ["Group-11"], Day.MONDAY, 1, WeekType.BOTH, "Building A")

        # Check if slot 3 in Building C is allowed (gap at slot 2, should be OK)
        is_valid, _, _ = tracker.check_building_gap_constraint(
            ["Group-11"], Day.MONDAY, 3, "Building C", WeekType.BOTH
        )
        assert is_valid is True

    def test_no_nearby_buildings_config(self):
        """Test behavior when no nearby buildings config is provided."""
        tracker = ConflictTracker(nearby_buildings=None)

        # Reserve slot 1 in Building A
        tracker.reserve("Instructor", ["Group-11"], Day.MONDAY, 1, WeekType.BOTH, "Building A")

        # Without config, different buildings should require gap
        is_valid, _, _ = tracker.check_building_gap_constraint(
            ["Group-11"], Day.MONDAY, 2, "Building C", WeekType.BOTH
        )
        assert is_valid is False

    def test_multiple_groups_one_has_conflict(self, nearby_buildings):
        """Test that if any group has a building conflict, it's detected."""
        tracker = ConflictTracker(nearby_buildings=nearby_buildings)

        # Only Group-11 has a class in Building A
        tracker.reserve("Instructor", ["Group-11"], Day.MONDAY, 1, WeekType.BOTH, "Building A")

        # Check for multiple groups including Group-11
        is_valid, conflicting_group, _ = tracker.check_building_gap_constraint(
            ["Group-11", "Group-13"], Day.MONDAY, 2, "Building C", WeekType.BOTH
        )
        assert is_valid is False
        assert conflicting_group == "Group-11"

    def test_different_day_no_conflict(self, nearby_buildings):
        """Test that building gap constraint is per-day."""
        tracker = ConflictTracker(nearby_buildings=nearby_buildings)

        # Reserve Monday slot 1 in Building A
        tracker.reserve("Instructor", ["Group-11"], Day.MONDAY, 1, WeekType.BOTH, "Building A")

        # Check Tuesday slot 2 in Building C (different day, should be OK)
        is_valid, _, _ = tracker.check_building_gap_constraint(
            ["Group-11"], Day.TUESDAY, 2, "Building C", WeekType.BOTH
        )
        assert is_valid is True

    def test_building_tracking_stored_correctly(self, nearby_buildings):
        """Test that building info is stored and retrieved correctly."""
        tracker = ConflictTracker(nearby_buildings=nearby_buildings)

        tracker.reserve("Instructor", ["Group-11"], Day.MONDAY, 1, WeekType.BOTH, "Building A")

        # Retrieve building info
        building = tracker.get_group_building_at_slot("Group-11", Day.MONDAY, 1, WeekType.BOTH)
        assert building == "Building A"

        # Non-existent slot should return None
        building = tracker.get_group_building_at_slot("Group-11", Day.MONDAY, 2, WeekType.BOTH)
        assert building is None
