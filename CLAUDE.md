# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Schedule Generator parses Form-1 (Ф-1) Excel workload spreadsheets from West Kazakhstan Innovation and Technological University and generates optimized lecture schedules. It extracts lecture, practical, and laboratory streams, then schedules multi-group lectures across Monday-Wednesday with room assignments.

## Commands

```bash
# Install dependencies
uv sync

# Parse Form-1 to JSON
uv run form1-parser parse data/form-1.xlsx -o output/result.json

# Generate schedule from parsed data
uv run form1-parser schedule output/result.json -o output/schedule.json

# Generate Excel schedule files
uv run form1-parser generate-excel output/schedule.json -o output/excel/

# Other commands
uv run form1-parser validate data/form-1.xlsx
uv run form1-parser stats data/form-1.xlsx

# Run all tests
uv run pytest tests/ -v

# Run single test file
uv run pytest tests/test_parser.py -v

# Run specific test
uv run pytest tests/test_models.py::test_weekly_hours_from_total -v

# Lint with ruff
uv run ruff check src/
uv run ruff format src/
```

## Architecture

### Pipeline Overview

```
Form-1 Excel → Parser → ParseResult JSON → Scheduler → ScheduleResult JSON → Excel Generator → Excel Files
```

### Parser Components

1. **CLI** (`cli.py`) → Typer entry point with 5 commands: parse, validate, stats, schedule, generate-excel
2. **Parser** (`parser.py`) → `Form1Parser` reads Excel sheets, finds data boundaries, groups by subject
3. **Pattern Detection** (`patterns.py`) → Detects which of 4 patterns a subject uses
4. **Extractors** (`extractors.py`) → Strategy pattern with 4 extractors, one per data pattern
5. **Exporters** (`exporters.py`) → JSON/CSV/Excel output via `get_exporter(format)` factory

### Scheduler Components (`scheduler/`)

1. **Algorithm** (`algorithm.py`) → `Stage1Scheduler` schedules lectures with 2+ groups to Mon/Tue/Wed
2. **Conflicts** (`conflicts.py`) → `ConflictTracker` prevents instructor/group/room double-booking
3. **Rooms** (`rooms.py`) → `RoomManager` handles room allocation with capacity buffers and priority
4. **Excel Generator** (`excel_generator.py`) → Creates formatted schedules per language/year/week_type

### Data Patterns

The parser handles 4 distinct patterns for how subjects organize their data:

- **1a** (Horizontal-Individual): Each row has its own practical/lab hours
- **1b** (Horizontal-Merged): NaN in prac/lab means merge with previous stream
- **implicit_subgroup**: Same group name repeated for lab subgroups
- **explicit_subgroup**: Groups with notation like `/1/`, `\1\`, `-1`

### Key Models

**Parser models** (`models.py`):
- `Stream`: Single academic stream (subject + type + instructor + groups)
- `WeeklyHours`: Calculates odd/even week hours from total using formula: `total = odd×8 + even×7`
- `SubjectSummary`: Groups streams by subject with detected pattern
- `ParseResult`: Complete parse output with streams, subjects, errors, warnings

**Scheduler models** (`scheduler/models.py`):
- `Assignment`: Scheduled class with day, slot, room
- `LectureStream`: Lecture prepared for scheduling with shift requirement
- `UnscheduledStream`: Stream that couldn't be scheduled with reason

### Sheet Processing

- Sheets are processed by name (defined in `SHEET_NAMES` constant)
- Data start row found by looking for "1" or "2 семестр" markers
- Instructor column varies per sheet (hardcoded in `KNOWN_INSTRUCTOR_COLUMNS`)
- Subject names are forward-filled since they span multiple group rows

### Scheduling Rules

- 13 time slots per day (9:00-21:50, 50 min each)
- First shift (slots 1-5): 1st and 3rd year students
- Second shift (slots 6-13): 2nd year students, 4th/5th year automatic
- Room priority: subject-specific → instructor-specific → group building → general pool
- Building gaps: requires 1 free slot when changing buildings
