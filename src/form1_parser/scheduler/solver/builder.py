"""CP-SAT model construction."""

from typing import TYPE_CHECKING

from ortools.sat.python import cp_model

from ..constraints.hard import HardConstraints
from ..constraints.soft import SoftConstraints
from ..models import LectureStream, Room, WeekType
from .variables import VariableManager

if TYPE_CHECKING:
    from ..config import ConfigLoader


class ModelBuilder:
    """Orchestrates CP-SAT model construction."""

    def __init__(
        self,
        config: "ConfigLoader",
        streams: list[LectureStream],
        rooms: list[Room],
        week_type: WeekType = WeekType.BOTH,
    ):
        self.config = config
        self.streams = streams
        self.rooms = rooms
        self.week_type = week_type

        self.model = cp_model.CpModel()
        self.variables: dict = {}
        self.variable_manager: VariableManager | None = None
        self.hard_constraints: HardConstraints | None = None
        self.soft_constraints: SoftConstraints | None = None

    def build(self) -> cp_model.CpModel:
        """
        Build the complete CP-SAT model.

        Returns the configured CpModel ready for solving.
        """
        # Create variables with domain reduction
        self.variable_manager = VariableManager(
            self.model,
            self.config,
            self.streams,
            self.rooms,
            self.week_type,
        )
        self.variables = self.variable_manager.create_variables()

        # Apply hard constraints
        self.hard_constraints = HardConstraints(
            self.model,
            self.config,
            self.streams,
            self.rooms,
        )
        self.hard_constraints.apply(self.variables)

        # Apply soft constraints (which adds the objective)
        self.soft_constraints = SoftConstraints(
            self.model,
            self.config,
            self.streams,
            self.rooms,
        )
        self.soft_constraints.apply(self.variables)

        # Add constraint to ensure each stream is assigned at most once
        self._add_single_assignment_constraint()

        return self.model

    def _add_single_assignment_constraint(self) -> None:
        """Ensure each hour of a stream is assigned to at most one time/room."""
        x = self.variables["x"]
        stream_hours = self.variables.get("stream_hours", {})

        for stream in self.streams:
            hours = stream_hours.get(stream.id, 1)

            for hour_idx in range(hours):
                # Get all variables for this stream and hour
                hour_vars = [
                    var for key, var in x.items()
                    if key[0] == stream.id and key[1] == hour_idx
                ]
                if hour_vars:
                    # At most one assignment per hour instance
                    self.model.AddAtMostOne(hour_vars)

    def get_variables(self) -> dict:
        """Get the variables dictionary."""
        return self.variables

    def get_model(self) -> cp_model.CpModel:
        """Get the CP-SAT model."""
        return self.model
