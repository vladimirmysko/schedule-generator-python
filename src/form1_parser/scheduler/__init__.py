"""Schedule generation module for Form-1 parser."""

from .algorithm import Stage1Scheduler, create_scheduler
from .conflicts import ConflictTracker
from .constants import (
    FIRST_SHIFT_SLOTS,
    SECOND_SHIFT_SLOTS,
    STAGE1_DAYS,
    STAGE1_MIN_GROUPS,
    TIME_SLOTS,
    YEAR_SHIFT_MAP,
    Shift,
    get_slot_info,
    get_slot_time_range,
    get_slots_for_shift,
)
from .excel_generator import (
    GeneratorConfig,
    ScheduleExcelGenerator,
    generate_schedule_excel,
)
from .exporter import export_schedule_json, load_parsed_data
from .models import (
    Assignment,
    Day,
    GroupInfo,
    LectureStream,
    Room,
    ScheduleResult,
    ScheduleStatistics,
    TimeSlot,
    WeekType,
)
from .rooms import RoomManager
from .utils import (
    clean_instructor_name,
    determine_shift,
    filter_stage1_lectures,
    parse_group_year,
    parse_specialty_code,
    sort_streams_by_priority,
)

__all__ = [
    # Algorithm
    "Stage1Scheduler",
    "create_scheduler",
    # Conflicts
    "ConflictTracker",
    # Constants
    "Shift",
    "TIME_SLOTS",
    "STAGE1_DAYS",
    "STAGE1_MIN_GROUPS",
    "FIRST_SHIFT_SLOTS",
    "SECOND_SHIFT_SLOTS",
    "YEAR_SHIFT_MAP",
    "get_slot_info",
    "get_slot_time_range",
    "get_slots_for_shift",
    # Excel Generator
    "GeneratorConfig",
    "ScheduleExcelGenerator",
    "generate_schedule_excel",
    # Exporter
    "export_schedule_json",
    "load_parsed_data",
    # Models
    "Day",
    "WeekType",
    "TimeSlot",
    "GroupInfo",
    "LectureStream",
    "Room",
    "Assignment",
    "ScheduleStatistics",
    "ScheduleResult",
    # Rooms
    "RoomManager",
    # Utils
    "parse_group_year",
    "parse_specialty_code",
    "determine_shift",
    "clean_instructor_name",
    "filter_stage1_lectures",
    "sort_streams_by_priority",
]
