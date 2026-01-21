# Stage 1: Multi-Group Lecture Scheduling

## Overview

Stage 1 handles scheduling of lectures with 2 or more groups. These are typically large lectures delivered to multiple student groups simultaneously. The scheduler prioritizes Monday, Tuesday, and Wednesday for these lectures, with Thursday and Friday as overflow days.

### Scope

- **Input**: Parsed Form-1 data (lecture streams with instructor, groups, and weekly hours)
- **Output**: Assigned time slots and rooms for each multi-group lecture
- **Days**: Monday-Wednesday (primary), Thursday-Friday (overflow)
- **Shifts**: First shift (09:00-13:50) and Second shift (14:00-21:50)

## Architecture

```
src/form1_parser/scheduler/
├── __init__.py          # Module exports
├── algorithm.py         # Stage1Scheduler - main scheduling algorithm
├── conflicts.py         # ConflictTracker - conflict detection
├── constants.py         # Time slots, shifts, stage days
├── excel_generator.py   # Excel output generation
├── exporter.py          # JSON export and data loading
├── models.py            # Data models (LectureStream, Assignment, etc.)
├── rooms.py             # RoomManager - room allocation
└── utils.py             # Filtering and sorting utilities
```

## Core Components

### Stage1Scheduler

**Location**: `src/form1_parser/scheduler/algorithm.py`

The main scheduling engine that orchestrates the entire scheduling process.

#### Initialization

```python
Stage1Scheduler(
    rooms_csv: Path,                    # Room definitions
    subject_rooms: dict | None,         # Subject-specific room requirements
    instructor_rooms: dict | None,      # Instructor room preferences
    group_buildings: dict | None,       # Specialty building assignments
    instructor_availability: list | None, # Instructor unavailability
    nearby_buildings: list | None       # Adjacent building groups
)
```

#### Main Method

```python
def schedule(streams: list[dict]) -> ScheduleResult
```

Process:
1. Filter streams to lectures with 2+ groups
2. Sort by priority (flexible subjects last, limited availability first, larger groups first)
3. Schedule each stream at optimal (day, slot) position
4. Compute statistics for the final result

#### Key Properties

| Property | Value | Description |
|----------|-------|-------------|
| `STAGE1_DAYS` | Mon, Tue, Wed | Primary scheduling days |
| `STAGE1_OVERFLOW_DAYS` | Thu, Fri | Overflow when primary days full |
| `STAGE1_MIN_GROUPS` | 2 | Minimum groups for Stage 1 |

### ConflictTracker

**Location**: `src/form1_parser/scheduler/conflicts.py`

Prevents scheduling conflicts by tracking occupied time slots.

#### Tracked Resources

| Resource | Key Structure | Purpose |
|----------|---------------|---------|
| Instructor schedule | `(day, slot, week_type) → set[instructor]` | Prevent double-booking instructors |
| Group schedule | `(day, slot, week_type) → set[group]` | Prevent group conflicts |
| Group daily load | `(group, day) → int` | Even distribution across days |
| Building schedule | `(group, day, slot, week_type) → address` | Building gap constraint |

#### Key Methods

| Method | Purpose |
|--------|---------|
| `is_instructor_available()` | Check instructor availability (includes weekly unavailability) |
| `are_groups_available()` | Check if all groups are free |
| `check_building_gap_constraint()` | Validate travel time between buildings |
| `reserve()` | Mark slot as occupied for instructor and groups |

#### UnscheduledReason Enum

When a stream cannot be scheduled, one of these reasons is provided:

| Reason | Description |
|--------|-------------|
| `INSTRUCTOR_CONFLICT` | Instructor already scheduled at this time |
| `INSTRUCTOR_UNAVAILABLE` | Instructor marked unavailable (from config) |
| `GROUP_CONFLICT` | One or more groups already have class |
| `NO_CONSECUTIVE_SLOTS` | Cannot find enough back-to-back slots |
| `NO_ROOM_AVAILABLE` | No room with sufficient capacity |
| `ALL_SLOTS_EXHAUSTED` | Tried all positions, none available |
| `BUILDING_GAP_REQUIRED` | Insufficient travel time between buildings |

### RoomManager

**Location**: `src/form1_parser/scheduler/rooms.py`

Handles room allocation with a 4-level priority system.

#### Room Selection Priority

1. **Subject-specific rooms** (from `subject-rooms.json`) - Strict requirement, no fallback
2. **Instructor preferences** (from `instructor-rooms.json`)
3. **Group building preferences** (from `group-buildings.json`) - Only if all groups share specialty
4. **General pool** - Find by capacity, respecting building access restrictions

#### Capacity Finding Logic

When selecting from the general pool:

1. Filter to available rooms (not occupied, not special unless allowed)
2. Check building access restrictions
3. **Primary**: Find smallest room with capacity ≥ student count
4. **Fallback**: Apply buffer for undersized rooms
   - Buffer: 50% for ≤30 students, 20% for ≥100 students, linear between
   - Example: 30 students, buffer = 15 → can use 18-seat room (18+15 ≥ 30)

### Data Models

**Location**: `src/form1_parser/scheduler/models.py`

#### Input Model: LectureStream

```python
@dataclass
class LectureStream:
    id: str
    subject: str
    instructor: str
    language: str
    groups: list[str]
    student_count: int
    hours_odd_week: int
    hours_even_week: int
    shift: Shift
    sheet: str
    instructor_available_slots: int = 0  # For priority sorting
    subject_prac_lab_hours: int = 0      # For priority sorting

    @property
    def max_hours(self) -> int:
        """Maximum hours needed (for consecutive slot allocation)"""
        return max(self.hours_odd_week, self.hours_even_week)
```

#### Output Model: Assignment

```python
@dataclass
class Assignment:
    stream_id: str
    subject: str
    instructor: str
    groups: list[str]
    student_count: int
    day: Day
    slot: int
    room: str           # Room name (e.g., "А-1")
    room_address: str   # Building address
    week_type: WeekType = WeekType.BOTH
```

#### Output Model: UnscheduledStream

```python
@dataclass
class UnscheduledStream:
    stream_id: str
    subject: str
    instructor: str
    groups: list[str]
    student_count: int
    shift: Shift
    reason: UnscheduledReason
    details: str = ""   # Additional context about failure
```

#### Result Container: ScheduleResult

```python
@dataclass
class ScheduleResult:
    generation_date: str
    stage: int
    assignments: list[Assignment]
    unscheduled_stream_ids: list[str]
    unscheduled_streams: list[UnscheduledStream]
    statistics: ScheduleStatistics
```

## Scheduling Algorithm

### Stage 1 Rules

1. **Filter**: Only lectures with 2+ groups
2. **Sort Priority**:
   - Flexible subjects (e.g., "Дене шынықтыру") scheduled last
   - Instructors with limited availability scheduled first
   - Complex subjects (with prac/lab hours) scheduled first
   - Larger student groups scheduled first
3. **Day Selection**: Mon/Tue/Wed preferred, Thu/Fri as overflow
4. **Even Distribution**: Balance lectures across days for each group
5. **Shift Alignment**: Lectures start at shift beginning
6. **Week Consistency**: Same (day, slot) for both odd and even weeks
7. **Multi-hour Handling**: If hours > 1, assign consecutive slots

### Position Finding Algorithm

For each stream, `_find_best_position()` executes:

1. Get valid slots for stream's shift
2. Determine allowed days (flexible subjects use all weekdays)
3. Sort days by total group load (prefer least loaded)
4. For each day (primary first, then overflow):
   - For each starting slot (earliest first):
     - Check instructor and group availability for all consecutive slots
     - Verify room availability for required capacity
     - Validate building gap constraint
     - If all pass, return (day, slot)
5. If no position found, return failure reason with details

### Constraint Validation

| Constraint | Check | Failure Reason |
|------------|-------|----------------|
| Instructor availability | `is_instructor_available()` | `INSTRUCTOR_UNAVAILABLE` |
| Instructor conflict | Existing reservation | `INSTRUCTOR_CONFLICT` |
| Group conflict | Existing reservation | `GROUP_CONFLICT` |
| Consecutive slots | All slots available | `NO_CONSECUTIVE_SLOTS` |
| Room capacity | Room fits students | `NO_ROOM_AVAILABLE` |
| Building gap | Travel time sufficient | `BUILDING_GAP_REQUIRED` |

## CLI Commands

### schedule

Generates Stage 1 schedule from parsed Form-1 data.

```bash
uv run form1-parser schedule <input_file> [OPTIONS]
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `-o, --output` | `output/schedule.json` | Output JSON file path |
| `--rooms` | `data/reference/rooms.csv` | Room definitions |
| `--subject-rooms` | None | Subject-specific rooms |
| `--instructor-rooms` | None | Instructor room preferences |
| `--group-buildings` | None | Specialty building mappings |
| `--instructor-availability` | None | Instructor unavailability |
| `--nearby-buildings` | None | Nearby building groups |
| `-v, --verbose` | False | Show detailed output |

**Example:**

```bash
uv run form1-parser schedule output/result.json \
    --rooms data/reference/rooms.csv \
    --group-buildings data/reference/group-buildings.json \
    --instructor-availability data/reference/instructor-availability.json \
    --nearby-buildings data/reference/nearby-buildings.json \
    -o output/schedule.json
```

### generate-excel

Creates Excel schedules from the generated JSON schedule.

```bash
uv run form1-parser generate-excel <input_file> [OPTIONS]
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `-o, --output` | `output/excel` | Output directory |
| `-l, --language` | All | Filter: 'kaz' or 'rus' |
| `-y, --year` | All | Filter: 1, 2, 3, or 4 |
| `-w, --week-type` | All | Filter: 'odd' or 'even' |
| `-v, --verbose` | False | Show detailed output |

**Output Files:**

```
output/excel/
├── schedule_kaz_1y_odd.xlsx
├── schedule_kaz_1y_even.xlsx
├── schedule_kaz_2y_odd.xlsx
├── schedule_rus_1y_odd.xlsx
└── ...
```

## Data Flow

```
┌─────────────────────┐
│   Form-1 Excel      │
│   (Ф-1 spreadsheet) │
└──────────┬──────────┘
           │ parse command
           ▼
┌─────────────────────┐
│   Parsed JSON       │
│   (streams list)    │
└──────────┬──────────┘
           │ schedule command
           ▼
┌─────────────────────┐
│   Stage1Scheduler   │
│   ┌───────────────┐ │
│   │ ConflictTracker│ │
│   │ RoomManager   │ │
│   └───────────────┘ │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   Schedule JSON     │
│   (assignments +    │
│    unscheduled)     │
└──────────┬──────────┘
           │ generate-excel command
           ▼
┌─────────────────────┐
│   Excel Files       │
│   (by lang/year/    │
│    week type)       │
└─────────────────────┘
```

## Reference Data

### rooms.csv

Room definitions with capacity and location.

| Column | Type | Description |
|--------|------|-------------|
| name | string | Room identifier (e.g., "А-1") |
| capacity | int | Maximum student capacity |
| address | string | Building address |
| is_special | bool | Special facility flag |

### group-buildings.json

Maps specialty codes to preferred building addresses.

```json
{
  "SPECIALTY_CODE": {
    "addresses": [
      { "address": "ул. Чапаева 69" },
      { "address": "ул. Ихсанова, 44/1", "rooms": ["201", "202"] }
    ]
  }
}
```

### instructor-availability.json

Tracks instructor weekly unavailability patterns.

```json
[
  {
    "name": "Instructor Name",
    "weekly_unavailable": {
      "friday": ["09:00", "10:00", "11:00"],
      "monday": ["09:00"]
    }
  }
]
```

### nearby-buildings.json

Groups buildings that are close enough for back-to-back classes.

```json
{
  "groups": [
    {
      "addresses": ["ул. Ихсанова, 44/1", "пр. Н.Назарбаева, 208"]
    }
  ]
}
```

### subject-rooms.json (optional)

Strict room requirements for specific subjects.

```json
{
  "Subject Name": {
    "lecture": [
      { "address": "ул. Ихсанова, 44/1", "room": "203 А" }
    ]
  }
}
```

### instructor-rooms.json (optional)

Instructor room preferences by class type.

```json
{
  "Instructor Name": {
    "lecture": [
      { "address": "ул. Ихсанова, 44/1", "room": "203 А" }
    ]
  }
}
```

## Key Files

| File | Purpose |
|------|---------|
| `src/form1_parser/scheduler/algorithm.py` | Stage1Scheduler class |
| `src/form1_parser/scheduler/conflicts.py` | ConflictTracker class |
| `src/form1_parser/scheduler/rooms.py` | RoomManager class |
| `src/form1_parser/scheduler/models.py` | Data models and enums |
| `src/form1_parser/scheduler/constants.py` | Time slots, shifts, stage days |
| `src/form1_parser/scheduler/utils.py` | Filtering and sorting utilities |
| `src/form1_parser/scheduler/exporter.py` | JSON export functions |
| `src/form1_parser/scheduler/excel_generator.py` | Excel generation |
| `src/form1_parser/cli.py` | CLI commands (schedule, generate-excel) |
| `data/reference/rooms.csv` | Room definitions |
| `data/reference/group-buildings.json` | Specialty building mappings |
| `data/reference/instructor-availability.json` | Instructor unavailability |
| `data/reference/nearby-buildings.json` | Adjacent building groups |

## Time Slots

### First Shift (Slots 1-5)

| Slot | Time |
|------|------|
| 1 | 09:00-09:50 |
| 2 | 10:00-10:50 |
| 3 | 11:00-11:50 |
| 4 | 12:00-12:50 |
| 5 | 13:00-13:50 |

### Second Shift (Slots 6-13)

| Slot | Time |
|------|------|
| 6 | 14:00-14:50 |
| 7 | 15:00-15:50 |
| 8 | 16:00-16:50 |
| 9 | 17:00-17:50 |
| 10 | 18:00-18:50 |
| 11 | 19:00-19:50 |
| 12 | 20:00-20:50 |
| 13 | 21:00-21:50 |

### Year-to-Shift Mapping

| Year | Shift |
|------|-------|
| 1st year | First (mandatory) |
| 2nd year | Second (mandatory) |
| 3rd year | First (default) |
| 4th/5th year | Second (default) |
