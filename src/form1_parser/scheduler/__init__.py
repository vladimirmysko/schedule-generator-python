"""University course scheduling system using OR-Tools CP-SAT solver.

This package provides a constraint-based scheduling algorithm for generating
optimized university schedules. It implements hard and soft constraints as
defined in the SCHEDULING_CONSTRAINTS.md specification.

Main classes:
- ORToolsScheduler: Main scheduler using CP-SAT solver
- Stage1Scheduler: Alias for ORToolsScheduler (backwards compatibility)
- ConfigLoader: Loads configuration from reference/ directory

Usage:
    from form1_parser.scheduler import ORToolsScheduler, WeekType

    scheduler = ORToolsScheduler(config_dir=Path("reference"))
    result = scheduler.schedule(streams, week_type=WeekType.BOTH)
"""

from .algorithm import Stage1Scheduler, create_scheduler
from .config import ConfigLoader
from .constants import (
    DEFAULT_TIME_LIMIT,
    FIRST_SHIFT_SLOTS,
    FLEXIBLE_SCHEDULE_SUBJECTS,
    MAX_SLOT,
    MIN_SLOT,
    SECOND_SHIFT_SLOTS,
    SOFT_CONSTRAINT_WEIGHTS,
    Shift,
)
from .models import (
    Assignment,
    Day,
    LectureStream,
    Room,
    ScheduleResult,
    ScheduleStatistics,
    StreamType,
    UnscheduledReason,
    UnscheduledStream,
    WeekType,
)
from .scheduler import ORToolsScheduler
from .utils import (
    filter_stage1_lectures,
    sort_streams_by_priority,
)

__all__ = [
    # Main scheduler
    "ORToolsScheduler",
    "Stage1Scheduler",
    "create_scheduler",
    # Configuration
    "ConfigLoader",
    # Models
    "Assignment",
    "Day",
    "LectureStream",
    "Room",
    "ScheduleResult",
    "ScheduleStatistics",
    "StreamType",
    "UnscheduledReason",
    "UnscheduledStream",
    "WeekType",
    # Constants
    "DEFAULT_TIME_LIMIT",
    "FIRST_SHIFT_SLOTS",
    "FLEXIBLE_SCHEDULE_SUBJECTS",
    "MAX_SLOT",
    "MIN_SLOT",
    "SECOND_SHIFT_SLOTS",
    "SOFT_CONSTRAINT_WEIGHTS",
    "Shift",
    # Utilities
    "filter_stage1_lectures",
    "sort_streams_by_priority",
]
