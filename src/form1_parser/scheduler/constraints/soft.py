"""Soft constraint implementations for the scheduler.

Soft constraints are preferences that should be satisfied when possible.
Violations result in penalty scores but do not invalidate the schedule.
"""

from typing import TYPE_CHECKING

from ortools.sat.python import cp_model

from ..constants import MAX_SLOT, MIN_SLOT, SOFT_CONSTRAINT_WEIGHTS
from ..models import Day, LectureStream, Room
from .base import ConstraintBase

if TYPE_CHECKING:
    from ..config import ConfigLoader


class SoftConstraints(ConstraintBase):
    """
    Implementation of soft constraints with weighted penalties.

    Soft Constraints (selected subset for initial implementation):
    - SC-01: Required Sessions Target (maximize scheduled streams)
    - SC-02: Minimize Student Gaps
    - SC-06: Building Transitions
    - SC-07: Minimize Instructor Gaps
    - SC-12: Instructor Room Preferences
    - SC-15: Lecture Before Practical
    """

    def __init__(
        self,
        model: cp_model.CpModel,
        config: "ConfigLoader",
        streams: list[LectureStream],
        rooms: list[Room],
    ):
        super().__init__(model, config, streams, rooms)
        self._stream_by_id = {s.id: s for s in streams}
        self._penalties: list[tuple[cp_model.IntVar, int]] = []

    def apply(self, variables: dict) -> None:
        """Apply all soft constraints to the model."""
        self._apply_scheduling_target(variables)
        self._apply_student_gap_penalty(variables)
        self._apply_instructor_gap_penalty(variables)
        self._apply_instructor_room_preference(variables)
        # Add objective to minimize total penalties
        self._add_objective()

    def get_penalties(self) -> list[tuple[cp_model.IntVar, int]]:
        """Get all penalty variables and their weights."""
        return self._penalties

    def _add_penalty(self, var: cp_model.IntVar, weight: int) -> None:
        """Add a penalty variable with its weight."""
        self._penalties.append((var, weight))

    def _add_objective(self) -> None:
        """Add the objective function to minimize total penalties."""
        if self._penalties:
            total_penalty = sum(var * weight for var, weight in self._penalties)
            self.model.Minimize(total_penalty)

    def _apply_scheduling_target(self, variables: dict) -> None:
        """
        SC-01: Required Sessions Target
        Maximize the number of scheduled streams.
        """
        x = variables["x"]
        scheduled = variables.get("scheduled", {})
        weight = SOFT_CONSTRAINT_WEIGHTS.get("SC-01", 180)

        # For each stream, create an indicator if it's scheduled
        for stream in self.streams:
            # Only check first hour (hour_idx=0) for scheduling status
            stream_vars = [
                var for key, var in x.items()
                if key[0] == stream.id and key[1] == 0
            ]
            if not stream_vars:
                continue

            # Check if stream is scheduled (any assignment)
            if stream.id in scheduled:
                is_scheduled = scheduled[stream.id]
            else:
                is_scheduled = self.model.NewBoolVar(f"scheduled_{stream.id}")
                self.model.AddMaxEquality(is_scheduled, stream_vars)
                scheduled[stream.id] = is_scheduled

            # Penalty for not scheduling
            not_scheduled = is_scheduled.Not()
            self._add_penalty(not_scheduled, weight)

    def _apply_student_gap_penalty(self, variables: dict) -> None:
        """
        SC-02: Minimize Student Idle Time (Gaps)
        Minimize gaps between consecutive classes for student groups.
        """
        x = variables["x"]
        weight = SOFT_CONSTRAINT_WEIGHTS.get("SC-02", 150)

        # Collect all groups
        all_groups: set[str] = set()
        for stream in self.streams:
            all_groups.update(stream.groups)

        for group in all_groups:
            for day in [Day.MONDAY, Day.TUESDAY, Day.WEDNESDAY, Day.THURSDAY, Day.FRIDAY]:
                # Get variables for each slot
                slot_vars: dict[int, list] = {s: [] for s in range(MIN_SLOT, MAX_SLOT + 1)}

                for key, var in x.items():
                    stream_id, hour_idx, var_day, var_slot, room_name, room_address = key
                    if var_day != day:
                        continue
                    stream = self._stream_by_id.get(stream_id)
                    if stream is None:
                        continue
                    if group in stream.groups:
                        slot_vars[var_slot].append(var)

                # Create indicator for each slot
                slot_has_class = {}
                for slot in range(MIN_SLOT, MAX_SLOT + 1):
                    if slot_vars[slot]:
                        slot_has_class[slot] = self.model.NewBoolVar(
                            f"shc_{group}_{day.name}_{slot}"
                        )
                        self.model.AddMaxEquality(slot_has_class[slot], slot_vars[slot])
                    else:
                        slot_has_class[slot] = self.model.NewConstant(0)

                # For each potential gap (slot between two classes)
                # Simplified: penalize empty slots between non-empty slots
                for slot in range(MIN_SLOT + 1, MAX_SLOT):
                    # Check if this could be a gap
                    # Gap: slot is empty, but there's a class before and after
                    if slot not in slot_has_class:
                        continue

                    # Find if there are any slots before and after with potential classes
                    has_before = any(slot_vars.get(s, []) for s in range(MIN_SLOT, slot))
                    has_after = any(slot_vars.get(s, []) for s in range(slot + 1, MAX_SLOT + 1))

                    if not has_before or not has_after:
                        continue

                    # Create gap indicator
                    gap = self.model.NewBoolVar(f"gap_{group}_{day.name}_{slot}")

                    # Gap is true if: current slot empty, AND some slot before has class,
                    # AND some slot after has class
                    # This is approximated: we just penalize empty slots in middle range
                    # More precise would require tracking first/last class

                    # Simplified: penalize if empty and adjacent slots have classes
                    prev_slot = slot - 1
                    next_slot = slot + 1

                    if prev_slot in slot_has_class and next_slot in slot_has_class:
                        # gap = NOT(current) AND prev AND next
                        self.model.AddBoolAnd([
                            slot_has_class[slot].Not(),
                            slot_has_class[prev_slot],
                            slot_has_class[next_slot]
                        ]).OnlyEnforceIf(gap)

                        self.model.AddBoolOr([
                            slot_has_class[slot],
                            slot_has_class[prev_slot].Not(),
                            slot_has_class[next_slot].Not()
                        ]).OnlyEnforceIf(gap.Not())

                        # Reduced weight per gap to avoid overwhelming the objective
                        self._add_penalty(gap, weight // 10)

    def _apply_instructor_gap_penalty(self, variables: dict) -> None:
        """
        SC-07: Minimize Instructor Idle Time
        Minimize gaps between classes in an instructor's daily schedule.
        """
        x = variables["x"]
        weight = SOFT_CONSTRAINT_WEIGHTS.get("SC-07", 80)

        # Collect all instructors
        instructors: set[str] = set()
        for stream in self.streams:
            instructors.add(stream.instructor)

        for instructor in instructors:
            for day in [Day.MONDAY, Day.TUESDAY, Day.WEDNESDAY, Day.THURSDAY, Day.FRIDAY]:
                # Get variables for each slot
                slot_vars: dict[int, list] = {s: [] for s in range(MIN_SLOT, MAX_SLOT + 1)}

                for key, var in x.items():
                    stream_id, hour_idx, var_day, var_slot, room_name, room_address = key
                    if var_day != day:
                        continue
                    stream = self._stream_by_id.get(stream_id)
                    if stream is None:
                        continue
                    if stream.instructor == instructor:
                        slot_vars[var_slot].append(var)

                # Similar logic to student gaps
                slot_has_class = {}
                for slot in range(MIN_SLOT, MAX_SLOT + 1):
                    if slot_vars[slot]:
                        slot_has_class[slot] = self.model.NewBoolVar(
                            f"ihc_{instructor[:10]}_{day.name}_{slot}"
                        )
                        self.model.AddMaxEquality(slot_has_class[slot], slot_vars[slot])

                # Penalize gaps (simplified)
                for slot in range(MIN_SLOT + 1, MAX_SLOT):
                    if slot not in slot_has_class:
                        continue
                    prev_slot = slot - 1
                    next_slot = slot + 1
                    if prev_slot in slot_has_class and next_slot in slot_has_class:
                        gap = self.model.NewBoolVar(
                            f"igap_{instructor[:10]}_{day.name}_{slot}"
                        )
                        self.model.AddBoolAnd([
                            slot_has_class[slot].Not(),
                            slot_has_class[prev_slot],
                            slot_has_class[next_slot]
                        ]).OnlyEnforceIf(gap)
                        self.model.AddBoolOr([
                            slot_has_class[slot],
                            slot_has_class[prev_slot].Not(),
                            slot_has_class[next_slot].Not()
                        ]).OnlyEnforceIf(gap.Not())
                        self._add_penalty(gap, weight // 10)

    def _apply_instructor_room_preference(self, variables: dict) -> None:
        """
        SC-12: Instructor Room Preferences
        Assign instructors to their preferred rooms when possible.
        """
        x = variables["x"]
        weight = SOFT_CONSTRAINT_WEIGHTS.get("SC-12", 75)

        for stream in self.streams:
            # Get instructor room preferences
            prefs = self.config.instructors.get_room_preferences(
                stream.instructor, stream.stream_type.value
            )
            if not prefs:
                continue

            # Get all variables for this stream
            stream_vars = [(key, var) for key, var in x.items() if key[0] == stream.id]
            if not stream_vars:
                continue

            # Separate preferred and non-preferred rooms
            preferred_vars = []
            non_preferred_vars = []

            for key, var in stream_vars:
                stream_id, hour_idx, day, slot, room_name, room_address = key
                if (room_address, room_name) in prefs:
                    preferred_vars.append(var)
                else:
                    non_preferred_vars.append(var)

            # Penalize non-preferred room assignments
            for var in non_preferred_vars:
                self._add_penalty(var, weight // len(non_preferred_vars) if non_preferred_vars else weight)
