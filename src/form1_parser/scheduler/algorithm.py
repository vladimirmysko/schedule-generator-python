"""Scheduling algorithm module (backwards compatibility).

This module provides the Stage1Scheduler class and factory function
for backwards compatibility with existing code and tests.
"""

from pathlib import Path

from .constants import DEFAULT_TIME_LIMIT, FLEXIBLE_SCHEDULE_SUBJECTS
from .models import Day, WeekType
from .scheduler import ORToolsScheduler, create_scheduler

# Re-export for backwards compatibility
Stage1Scheduler = ORToolsScheduler

__all__ = [
    "Stage1Scheduler",
    "create_scheduler",
    "FLEXIBLE_SCHEDULE_SUBJECTS",
]
