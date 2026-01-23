"""CP-SAT variable creation and domain reduction."""

from typing import TYPE_CHECKING

from ortools.sat.python import cp_model

from ..constants import FIRST_SHIFT_SLOTS, MAX_SLOT, MIN_SLOT, SECOND_SHIFT_SLOTS
from ..models import Day, LectureStream, Room, WeekType
from ..utils import (
    get_effective_capacity,
    get_shift_for_groups,
    get_all_specialties,
    is_flexible_subject,
    is_same_specialty_stream,
    parse_group_year,
)

if TYPE_CHECKING:
    from ..config import ConfigLoader


class VariableManager:
    """Creates and manages CP-SAT decision variables with domain reduction."""

    def __init__(
        self,
        model: cp_model.CpModel,
        config: "ConfigLoader",
        streams: list[LectureStream],
        rooms: list[Room],
        week_type: WeekType = WeekType.BOTH,
    ):
        self.model = model
        self.config = config
        self.streams = streams
        self.rooms = rooms
        self.week_type = week_type

        # Variable dictionaries
        # x[(stream_id, hour_idx, day, slot, room_name, room_address)] = BoolVar
        # hour_idx is 0-based index for multi-hour streams
        self.x: dict[tuple[str, int, Day, int, str, str], cp_model.IntVar] = {}

        # Auxiliary variables
        self.scheduled: dict[str, cp_model.IntVar] = {}  # stream_id -> is_scheduled

        # Track hours per stream
        self.stream_hours: dict[str, int] = {}

    def create_variables(self) -> dict:
        """
        Create decision variables with domain reduction.

        Returns a dictionary containing all variable types:
        - 'x': Primary decision variables (assignment indicators)
        - 'scheduled': Whether each stream is scheduled
        - 'stream_hours': Number of hours per stream
        """
        self._create_assignment_variables()
        self._create_scheduled_variables()
        self._add_multi_hour_constraints()

        return {
            "x": self.x,
            "scheduled": self.scheduled,
            "stream_hours": self.stream_hours,
        }

    def _get_hours_for_stream(self, stream: LectureStream) -> int:
        """Get number of hours needed for a stream."""
        if self.week_type == WeekType.ODD:
            return max(1, stream.hours_odd)
        elif self.week_type == WeekType.EVEN:
            return max(1, stream.hours_even)
        else:
            return max(1, stream.hours_odd, stream.hours_even)

    def _create_assignment_variables(self) -> None:
        """Create x variables with domain reduction."""
        for stream in self.streams:
            # Get number of hours for this stream
            hours = self._get_hours_for_stream(stream)
            self.stream_hours[stream.id] = hours

            # Get allowed days for this stream
            allowed_days = self._get_allowed_days(stream)

            # Get allowed slots based on shift
            allowed_slots = self._get_allowed_slots(stream)

            # Get allowed rooms based on constraints
            allowed_rooms = self._get_allowed_rooms(stream)

            if not allowed_days or not allowed_slots or not allowed_rooms:
                # Stream cannot be scheduled - no valid combinations
                continue

            # Create variables for each hour instance
            for hour_idx in range(hours):
                for day in allowed_days:
                    # Check instructor availability on this day
                    unavailable_slots = self.config.instructors.get_unavailable_slots(
                        stream.instructor, day
                    )

                    for slot in allowed_slots:
                        # Skip if instructor unavailable
                        if slot in unavailable_slots:
                            continue

                        # Check instructor day constraints
                        if not self._check_instructor_day_constraint(stream, day):
                            continue

                        for room in allowed_rooms:
                            # Create the variable
                            var_name = f"x_{stream.id}_h{hour_idx}_{day.name}_{slot}_{room.name}"
                            var = self.model.NewBoolVar(var_name)
                            self.x[(stream.id, hour_idx, day, slot, room.name, room.address)] = var

    def _create_scheduled_variables(self) -> None:
        """Create scheduled indicator variables."""
        for stream in self.streams:
            # Check if first hour is scheduled (all hours should be scheduled together)
            stream_vars = [
                var for key, var in self.x.items()
                if key[0] == stream.id and key[1] == 0
            ]

            if stream_vars:
                scheduled_var = self.model.NewBoolVar(f"scheduled_{stream.id}")
                self.model.AddMaxEquality(scheduled_var, stream_vars)
                self.scheduled[stream.id] = scheduled_var
            else:
                # Stream has no valid assignments
                self.scheduled[stream.id] = self.model.NewConstant(0)

    def _add_multi_hour_constraints(self) -> None:
        """Add constraints for multi-hour streams."""
        for stream in self.streams:
            hours = self.stream_hours.get(stream.id, 1)
            if hours <= 1:
                continue

            # For multi-hour streams, ensure all hours are scheduled
            # on the same day, in consecutive slots, in the same room

            # Get all first-hour assignments
            first_hour_vars = {
                (key[2], key[3], key[4], key[5]): var  # (day, slot, room_name, room_address)
                for key, var in self.x.items()
                if key[0] == stream.id and key[1] == 0
            }

            for hour_idx in range(1, hours):
                # Each subsequent hour must have exactly one assignment
                # that matches the first hour's day and room, with consecutive slot

                for (day, slot, room_name, room_address), first_var in first_hour_vars.items():
                    next_slot = slot + hour_idx

                    # Look for matching variable for this hour
                    next_key = (stream.id, hour_idx, day, next_slot, room_name, room_address)
                    if next_key in self.x:
                        next_var = self.x[next_key]
                        # If first hour is at this slot, subsequent hour must be at next slot
                        self.model.AddImplication(first_var, next_var)
                    else:
                        # No valid next slot - first hour at this position is invalid
                        self.model.Add(first_var == 0)

    def _get_allowed_days(self, stream: LectureStream) -> list[Day]:
        """
        Get allowed days for a stream (domain reduction).

        - Flexible subjects (PE): All weekdays
        - Regular subjects: Mon-Wed preferred, Thu-Fri overflow
        """
        if is_flexible_subject(stream.subject):
            return [Day.MONDAY, Day.TUESDAY, Day.WEDNESDAY, Day.THURSDAY, Day.FRIDAY]

        # For regular subjects, allow all weekdays but soft preference will handle ordering
        return [Day.MONDAY, Day.TUESDAY, Day.WEDNESDAY, Day.THURSDAY, Day.FRIDAY]

    def _get_allowed_slots(self, stream: LectureStream) -> list[int]:
        """
        Get allowed slots based on shift assignment (HC-11).
        """
        shift = get_shift_for_groups(stream.groups)

        # Check for second shift overrides
        for group in stream.groups:
            if self.config.groups.is_second_shift_group(group):
                return list(SECOND_SHIFT_SLOTS)

        if shift.value == 1:  # FIRST
            return list(FIRST_SHIFT_SLOTS)
        else:
            return list(SECOND_SHIFT_SLOTS)

    def _get_allowed_rooms(self, stream: LectureStream) -> list[Room]:
        """
        Get allowed rooms based on capacity and constraints.

        Applies:
        - HC-04: Room capacity with buffer
        - HC-05: Special room restrictions
        - HC-06: Subject-specific room requirements
        - HC-24: Specialty building exclusivity
        """
        candidate_rooms = []

        # Check for subject-specific room requirements (highest priority)
        subject_rooms = self.config.subjects.get_required_rooms(
            stream.subject, stream.stream_type.value
        )

        if subject_rooms:
            # Only allow specified rooms
            for address, room_name in subject_rooms:
                room = self.config.rooms.get_room(room_name, address)
                if room and self._room_fits_capacity(room, stream.student_count):
                    candidate_rooms.append(room)
            return candidate_rooms

        # Check specialty building exclusivity
        specialty_addresses = self._get_specialty_addresses(stream)

        # Get all rooms and filter
        for room in self.rooms:
            # Skip special rooms unless specifically required
            if room.is_special:
                continue

            # Check specialty building constraint
            if specialty_addresses is not None:
                if room.address not in specialty_addresses:
                    continue

            # Check capacity
            if not self._room_fits_capacity(room, stream.student_count):
                continue

            candidate_rooms.append(room)

        return candidate_rooms

    def _room_fits_capacity(self, room: Room, student_count: int) -> bool:
        """Check if room fits the stream with buffer."""
        effective_capacity = get_effective_capacity(room.capacity, student_count)
        return effective_capacity >= student_count

    def _get_specialty_addresses(self, stream: LectureStream) -> list[str] | None:
        """
        Get allowed addresses based on specialty building exclusivity (HC-24).

        Returns None if no restrictions.
        """
        # Only apply if all groups are same specialty
        if not is_same_specialty_stream(stream.groups):
            return None

        specialties = get_all_specialties(stream.groups)
        if not specialties:
            return None

        specialty = next(iter(specialties))
        return self.config.groups.get_specialty_addresses(specialty)

    def _check_instructor_day_constraint(self, stream: LectureStream, day: Day) -> bool:
        """
        Check if instructor can teach on this day (HC-14).

        Returns True if allowed.
        """
        # Get year of groups
        years = [parse_group_year(g) for g in stream.groups]
        valid_years = [y for y in years if y is not None]

        if not valid_years:
            return True  # No year info, allow

        # Check for each year
        for year in set(valid_years):
            allowed_days = self.config.instructors.get_allowed_days_for_year(
                stream.instructor, year
            )
            if allowed_days is not None:
                if day not in allowed_days:
                    return False

        return True

    def get_stream_variables(self, stream_id: str) -> list[tuple[tuple, cp_model.IntVar]]:
        """Get all variables for a specific stream."""
        return [(key, var) for key, var in self.x.items() if key[0] == stream_id]
