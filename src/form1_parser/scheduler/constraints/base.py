"""Base class for constraint implementations."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ortools.sat.python import cp_model

    from ..config import ConfigLoader
    from ..models import LectureStream, Room


class ConstraintBase(ABC):
    """Abstract base class for constraint implementations."""

    def __init__(
        self,
        model: "cp_model.CpModel",
        config: "ConfigLoader",
        streams: list["LectureStream"],
        rooms: list["Room"],
    ):
        """
        Initialize constraint handler.

        Args:
            model: The CP-SAT model to add constraints to.
            config: Configuration loader with room/instructor/subject configs.
            streams: List of streams to schedule.
            rooms: List of available rooms.
        """
        self.model = model
        self.config = config
        self.streams = streams
        self.rooms = rooms

    @abstractmethod
    def apply(self, variables: dict) -> None:
        """
        Apply the constraints to the model.

        Args:
            variables: Dictionary containing the CP-SAT decision variables.
        """
        pass
