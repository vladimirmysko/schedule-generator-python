"""Main scheduler class using OR-Tools CP-SAT solver."""

import logging
from pathlib import Path
from typing import Any

from ortools.sat.python import cp_model

from .config import ConfigLoader
from .constants import DEFAULT_TIME_LIMIT
from .models import (
    Day,
    LectureStream,
    Room,
    ScheduleResult,
    ScheduleStatistics,
    UnscheduledReason,
    UnscheduledStream,
    WeekType,
)
from .solver.builder import ModelBuilder
from .solver.extractor import FailureAnalyzer, SolutionExtractor
from .utils import filter_stage1_lectures, sort_streams_by_priority

logger = logging.getLogger(__name__)


class ORToolsScheduler:
    """
    University course scheduler using OR-Tools CP-SAT solver.

    This scheduler implements the constraint programming approach for
    generating optimal university schedules based on the constraints
    defined in SCHEDULING_CONSTRAINTS.md.
    """

    def __init__(
        self,
        config_dir_or_rooms_csv: Path | None = None,
        time_limit: int = DEFAULT_TIME_LIMIT,
    ):
        """
        Initialize the scheduler.

        Args:
            config_dir_or_rooms_csv: Path to directory containing configuration files,
                                    or path to rooms.csv file directly.
                                    Defaults to 'reference/' directory.
            time_limit: Maximum solving time in seconds.
        """
        # Determine if path is a directory or a CSV file
        if config_dir_or_rooms_csv is not None:
            path = Path(config_dir_or_rooms_csv)
            if path.is_file() and path.suffix == ".csv":
                # It's a rooms.csv file - use its directory as config dir
                self.config = ConfigLoader(
                    config_dir=path.parent,
                    rooms_csv=path,
                )
            else:
                # It's a directory
                self.config = ConfigLoader(config_dir=path)
        else:
            self.config = ConfigLoader()

        self.time_limit = time_limit

    def _is_flexible_subject(self, subject: str) -> bool:
        """Check if a subject has flexible scheduling (can use any weekday)."""
        from .utils import is_flexible_subject
        return is_flexible_subject(subject)

    def _get_allowed_days(self, subject: str) -> tuple[list[Day], list[Day]]:
        """
        Get allowed days for a subject.

        Returns:
            Tuple of (primary_days, overflow_days).
            For flexible subjects, all weekdays are primary and overflow is empty.
        """
        if self._is_flexible_subject(subject):
            # Flexible subjects can use all weekdays
            return (
                [Day.MONDAY, Day.TUESDAY, Day.WEDNESDAY, Day.THURSDAY, Day.FRIDAY],
                [],
            )
        else:
            # Regular subjects: Mon-Wed primary, Thu-Fri overflow
            return (
                [Day.MONDAY, Day.TUESDAY, Day.WEDNESDAY],
                [Day.THURSDAY, Day.FRIDAY],
            )

    def schedule(
        self,
        streams: list[dict[str, Any]],
        week_type: WeekType = WeekType.BOTH,
    ) -> ScheduleResult:
        """
        Schedule streams using the CP-SAT solver.

        Args:
            streams: List of stream dictionaries from parsed Form-1 data.
            week_type: Which week type to schedule (odd, even, or both).

        Returns:
            ScheduleResult containing assignments and unscheduled streams.
        """
        # Filter and prepare streams for Stage 1 scheduling
        lecture_streams = filter_stage1_lectures(streams)
        sorted_streams = sort_streams_by_priority(lecture_streams)

        if not sorted_streams:
            logger.warning("No eligible streams for Stage 1 scheduling")
            return ScheduleResult(week_type=week_type)

        logger.info(f"Scheduling {len(sorted_streams)} streams with {self.time_limit}s time limit")

        # Get available rooms
        rooms = self.config.rooms.get_regular_rooms()
        if not rooms:
            logger.error("No rooms available for scheduling")
            return self._create_all_unscheduled_result(sorted_streams, week_type)

        logger.info(f"Using {len(rooms)} rooms for scheduling")

        # Build the CP-SAT model
        builder = ModelBuilder(self.config, sorted_streams, rooms, week_type)
        model = builder.build()
        variables = builder.get_variables()

        # Create and configure solver
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.time_limit
        solver.parameters.log_search_progress = False

        # Solve
        logger.info("Starting CP-SAT solver...")
        status = solver.Solve(model)

        # Handle different solver statuses
        if status == cp_model.OPTIMAL:
            logger.info("Found optimal solution")
        elif status == cp_model.FEASIBLE:
            logger.info("Found feasible solution (may not be optimal)")
        elif status == cp_model.INFEASIBLE:
            logger.warning("Problem is infeasible - analyzing failures")
            analyzer = FailureAnalyzer(self.config, sorted_streams, rooms)
            issues = analyzer.analyze_infeasibility()
            for issue in issues:
                logger.warning(f"  - {issue}")
            return self._create_infeasible_result(sorted_streams, week_type)
        else:
            logger.warning(f"Solver returned status: {solver.StatusName(status)}")
            return self._create_timeout_result(sorted_streams, week_type)

        # Extract solution
        extractor = SolutionExtractor(
            solver, variables, sorted_streams, rooms, self.config, week_type
        )
        result = extractor.extract()

        logger.info(
            f"Scheduled {result.total_assigned} of {len(sorted_streams)} streams "
            f"({100 * result.total_assigned / len(sorted_streams):.1f}%)"
        )

        return result

    def _create_all_unscheduled_result(
        self,
        streams: list[LectureStream],
        week_type: WeekType,
    ) -> ScheduleResult:
        """Create result where all streams are unscheduled."""
        unscheduled = [
            UnscheduledStream(
                stream_id=s.id,
                subject=s.subject,
                stream_type=s.stream_type,
                instructor=s.instructor,
                groups=s.groups,
                student_count=s.student_count,
                reason=UnscheduledReason.NO_ROOM_AVAILABLE,
                details="No rooms available for scheduling",
            )
            for s in streams
        ]
        return ScheduleResult(
            unscheduled_streams=unscheduled,
            statistics=ScheduleStatistics(
                total_streams=len(streams),
                total_unscheduled=len(streams),
            ),
            week_type=week_type,
        )

    def _create_infeasible_result(
        self,
        streams: list[LectureStream],
        week_type: WeekType,
    ) -> ScheduleResult:
        """Create result for infeasible problem."""
        unscheduled = [
            UnscheduledStream(
                stream_id=s.id,
                subject=s.subject,
                stream_type=s.stream_type,
                instructor=s.instructor,
                groups=s.groups,
                student_count=s.student_count,
                reason=UnscheduledReason.INFEASIBLE,
                details="No feasible schedule exists with current constraints",
            )
            for s in streams
        ]
        return ScheduleResult(
            unscheduled_streams=unscheduled,
            statistics=ScheduleStatistics(
                total_streams=len(streams),
                total_unscheduled=len(streams),
            ),
            week_type=week_type,
        )

    def _create_timeout_result(
        self,
        streams: list[LectureStream],
        week_type: WeekType,
    ) -> ScheduleResult:
        """Create result for solver timeout."""
        unscheduled = [
            UnscheduledStream(
                stream_id=s.id,
                subject=s.subject,
                stream_type=s.stream_type,
                instructor=s.instructor,
                groups=s.groups,
                student_count=s.student_count,
                reason=UnscheduledReason.SOLVER_TIMEOUT,
                details=f"Solver exceeded time limit ({self.time_limit}s)",
            )
            for s in streams
        ]
        return ScheduleResult(
            unscheduled_streams=unscheduled,
            statistics=ScheduleStatistics(
                total_streams=len(streams),
                total_unscheduled=len(streams),
            ),
            week_type=week_type,
        )


# Backwards compatibility alias
Stage1Scheduler = ORToolsScheduler


def create_scheduler(
    rooms_csv: Path,
    subject_rooms_path: Path | None = None,
    instructor_rooms_path: Path | None = None,
    time_limit: int = DEFAULT_TIME_LIMIT,
) -> ORToolsScheduler:
    """
    Factory function to create a scheduler.

    Args:
        rooms_csv: Path to rooms.csv file.
        subject_rooms_path: Optional path to subject-rooms.json.
        instructor_rooms_path: Optional path to instructor-rooms.json.
        time_limit: Maximum solving time in seconds.

    Returns:
        Configured ORToolsScheduler instance.
    """
    # Pass rooms_csv directly - scheduler will detect it's a file
    return ORToolsScheduler(config_dir_or_rooms_csv=rooms_csv, time_limit=time_limit)
