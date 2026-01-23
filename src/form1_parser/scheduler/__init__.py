"""Schedule generation module for Form-1 parser."""

from .algorithm import (
    Stage1Scheduler,
    Stage2Scheduler,
    create_scheduler,
    create_stage2_scheduler,
)
from .stage3 import (
    Stage3Scheduler,
    create_stage3_scheduler,
)
from .stage4 import (
    Stage4Scheduler,
    create_stage4_scheduler,
)
from .stage5 import (
    Stage5Scheduler,
    create_stage5_scheduler,
)
from .stage6 import (
    Stage6Scheduler,
    create_stage6_scheduler,
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
    Stage3PracticalStream,
    Stage4LectureStream,
    Stage5PracticalStream,
    Stage6LabStream,
    TimeSlot,
    WeekType,
)
from .rooms import RoomManager
from .utils import (
    build_lecture_dependency_map,
    build_scheduled_lecture_days,
    build_stage5_subgroup_pairs,
    build_stage6_subgroup_pairs,
    build_subgroup_pairs,
    calculate_stage3_complexity_score,
    calculate_stage4_complexity_score,
    calculate_stage5_complexity_score,
    calculate_stage6_complexity_score,
    categorize_stage6_labs,
    clean_instructor_name,
    determine_shift,
    filter_stage1_lectures,
    filter_stage2_practicals,
    filter_stage3_practicals,
    filter_stage4_lectures,
    filter_stage5_practicals,
    filter_stage6_labs,
    parse_group_year,
    parse_specialty_code,
    parse_subgroup_info,
    sort_practicals_by_complexity,
    sort_stage3_by_complexity,
    sort_stage4_by_complexity,
    sort_stage5_by_complexity,
    sort_stage6_by_complexity,
    sort_streams_by_priority,
)

__all__ = [
    # Algorithm
    "Stage1Scheduler",
    "Stage2Scheduler",
    "Stage3Scheduler",
    "Stage4Scheduler",
    "Stage5Scheduler",
    "Stage6Scheduler",
    "create_scheduler",
    "create_stage2_scheduler",
    "create_stage3_scheduler",
    "create_stage4_scheduler",
    "create_stage5_scheduler",
    "create_stage6_scheduler",
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
    "Stage3PracticalStream",
    "Stage4LectureStream",
    "Stage5PracticalStream",
    "Stage6LabStream",
    "Room",
    "Assignment",
    "ScheduleStatistics",
    "ScheduleResult",
    # Rooms
    "RoomManager",
    # Utils
    "parse_group_year",
    "parse_specialty_code",
    "parse_subgroup_info",
    "determine_shift",
    "clean_instructor_name",
    "filter_stage1_lectures",
    "filter_stage2_practicals",
    "filter_stage3_practicals",
    "filter_stage4_lectures",
    "filter_stage5_practicals",
    "filter_stage6_labs",
    "sort_streams_by_priority",
    "sort_practicals_by_complexity",
    "sort_stage3_by_complexity",
    "sort_stage4_by_complexity",
    "sort_stage5_by_complexity",
    "sort_stage6_by_complexity",
    "build_lecture_dependency_map",
    "build_scheduled_lecture_days",
    "build_subgroup_pairs",
    "build_stage5_subgroup_pairs",
    "build_stage6_subgroup_pairs",
    "calculate_stage3_complexity_score",
    "calculate_stage4_complexity_score",
    "calculate_stage5_complexity_score",
    "calculate_stage6_complexity_score",
    "categorize_stage6_labs",
]
