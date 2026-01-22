"""Schedule generation module for Form-1 parser."""

from .algorithm import (
    Stage1Scheduler,
    Stage2Scheduler,
    create_scheduler,
    create_stage2_scheduler,
)
from .conflicts import ConflictTracker
from .constants import (
    FIRST_SHIFT_EXTENDED_SLOTS,
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
from .instructor_excel_generator import (
    InstructorGeneratorConfig,
    InstructorScheduleExcelGenerator,
    generate_instructor_schedule_excel,
)
from .exporter import export_schedule_json, load_parsed_data
from .models import (
    Assignment,
    Day,
    GroupInfo,
    LectureDependency,
    LectureStream,
    PracticalStream,
    Room,
    ScheduleResult,
    ScheduleStatistics,
    TimeSlot,
    WeekType,
)
from .rooms import RoomManager
from .utils import (
    build_lecture_dependency_map,
    clean_instructor_name,
    determine_shift,
    filter_stage1_lectures,
    filter_stage2_practicals,
    parse_group_year,
    parse_specialty_code,
    sort_practicals_by_complexity,
    sort_streams_by_priority,
)

__all__ = [
    # Algorithm
    "Stage1Scheduler",
    "Stage2Scheduler",
    "create_scheduler",
    "create_stage2_scheduler",
    # Conflicts
    "ConflictTracker",
    # Constants
    "Shift",
    "TIME_SLOTS",
    "STAGE1_DAYS",
    "STAGE1_MIN_GROUPS",
    "FIRST_SHIFT_SLOTS",
    "FIRST_SHIFT_EXTENDED_SLOTS",
    "SECOND_SHIFT_SLOTS",
    "YEAR_SHIFT_MAP",
    "get_slot_info",
    "get_slot_time_range",
    "get_slots_for_shift",
    # Excel Generator
    "GeneratorConfig",
    "ScheduleExcelGenerator",
    "generate_schedule_excel",
    # Instructor Excel Generator
    "InstructorGeneratorConfig",
    "InstructorScheduleExcelGenerator",
    "generate_instructor_schedule_excel",
    # Exporter
    "export_schedule_json",
    "load_parsed_data",
    # Models
    "Day",
    "WeekType",
    "TimeSlot",
    "GroupInfo",
    "LectureDependency",
    "LectureStream",
    "PracticalStream",
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
    "filter_stage2_practicals",
    "sort_streams_by_priority",
    "sort_practicals_by_complexity",
    "build_lecture_dependency_map",
]
