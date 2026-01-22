# Form-1 Parser

Parser for Form-1 (Ф-1) Excel workload spreadsheets from West Kazakhstan Innovation and Technological University. Extracts lecture, practical, and laboratory streams with instructors from department sheets.

## Installation

```bash
uv sync
```

## Usage

### Parse

Parse a Form-1 Excel file and extract streams.

```bash
uv run form1-parser parse <INPUT_FILE> [OPTIONS]
```

**Arguments:**
- `INPUT_FILE` - Path to the Form-1 Excel file (required)

**Options:**
- `-o, --output PATH` - Output file or directory path
- `-f, --format [json|csv|excel]` - Output format (default: json)
- `-v, --verbose` - Show detailed output

**Examples:**

```bash
# Parse to JSON (default)
uv run form1-parser parse data/form-1.xlsx -o output/result.json

# Parse to CSV
uv run form1-parser parse data/form-1.xlsx -o output/ -f csv

# Parse to Excel
uv run form1-parser parse data/form-1.xlsx -o output/result.xlsx -f excel

# Parse with verbose output
uv run form1-parser parse data/form-1.xlsx -o output/result.json -v
```

### Validate

Validate a Form-1 file structure without full parsing.

```bash
uv run form1-parser validate <INPUT_FILE>
```

**Arguments:**
- `INPUT_FILE` - Path to the Form-1 Excel file (required)

**Example:**

```bash
uv run form1-parser validate data/form-1.xlsx
```

### Stats

Show detailed statistics for a Form-1 file.

```bash
uv run form1-parser stats <INPUT_FILE>
```

**Arguments:**
- `INPUT_FILE` - Path to the Form-1 Excel file (required)

**Example:**

```bash
uv run form1-parser stats data/form-1.xlsx
```

### Schedule

Generate Stage 1 schedule for multi-group lectures. This command takes the parsed JSON output and creates a schedule assigning lectures to Monday, Tuesday, and Wednesday.

```bash
uv run form1-parser schedule <INPUT_FILE> [OPTIONS]
```

**Arguments:**
- `INPUT_FILE` - Parsed JSON file from `form1-parser parse` command (required)

**Options:**
- `-o, --output PATH` - Output JSON file path (default: output/schedule.json)
- `--rooms PATH` - Path to rooms.csv file (default: data/reference/rooms.csv)
- `--subject-rooms PATH` - Path to subject-rooms.json file (default: data/reference/subject-rooms.json)
- `--instructor-rooms PATH` - Path to instructor-rooms.json file (default: data/reference/instructor-rooms.json)
- `--group-buildings PATH` - Path to group-buildings.json file (default: data/reference/group-buildings.json)
- `-v, --verbose` - Show detailed output including room utilization and unscheduled streams

**Examples:**

```bash
# Generate schedule with default settings
uv run form1-parser schedule output/result.json

# Generate schedule with custom output path
uv run form1-parser schedule output/result.json -o output/schedule.json

# Generate schedule with verbose output
uv run form1-parser schedule output/result.json -v

# Generate schedule with custom reference files
uv run form1-parser schedule output/result.json --rooms custom/rooms.csv
```

**Stage 1 Algorithm:**
- Filters lectures with 2+ groups
- Sorts by student count (largest first)
- Assigns to Monday, Tuesday, Wednesday only
- Distributes evenly across days
- Assigns rooms based on priority: subject rooms → instructor rooms → group buildings → general pool

### Generate Excel

Generate formatted Excel schedule files from schedule JSON. Creates separate files for each combination of language, year, and week type.

```bash
uv run form1-parser generate-excel <INPUT_FILE> [OPTIONS]
```

**Arguments:**
- `INPUT_FILE` - Schedule JSON file from `form1-parser schedule` command (required)

**Options:**
- `-o, --output PATH` - Output directory for Excel files (default: output/excel/)
- `-l, --language [kaz|rus]` - Filter by language (Kazakh or Russian)
- `-y, --year [1|2|3|4]` - Filter by student year
- `-w, --week-type [odd|even]` - Filter by week type
- `-v, --verbose` - Show detailed output

**Examples:**

```bash
# Generate all combinations (kaz/rus × years 1-4 × odd/even)
uv run form1-parser generate-excel output/schedule.json -o output/excel/

# Generate specific file
uv run form1-parser generate-excel output/schedule.json -l kaz -y 1 -w odd

# Generate all Kazakh schedules
uv run form1-parser generate-excel output/schedule.json -l kaz

# Generate all 2nd year schedules
uv run form1-parser generate-excel output/schedule.json -y 2
```

**Output Files:**

Files are named: `schedule_{language}_{year}y_{week_type}.xlsx`

Examples:
- `schedule_kaz_1y_odd.xlsx` - Kazakh, 1st year, odd weeks
- `schedule_rus_2y_even.xlsx` - Russian, 2nd year, even weeks

**Language Detection:**

Language is determined by the second digit of the group code:
- Odd (1, 3, 5, 7, 9) → Kazakh (e.g., `АРХ-11 О`, `ЮР-33 О`)
- Even (2, 4, 6, 8, 0) → Russian (e.g., `АРХ-22 О`, `СТР-24 О`)

### Generate Instructor Excel

Generate Excel schedule files organized by instructor. Creates one sheet per instructor with days on rows and time slots on columns. Includes color coding for odd/even weeks.

```bash
uv run form1-parser generate-instructor-excel <INPUT_FILE> [OPTIONS]
```

**Arguments:**
- `INPUT_FILE` - Schedule JSON file from `form1-parser schedule` command (required)

**Options:**
- `-o, --output PATH` - Output directory for Excel files (default: output/instructors/)
- `-l, --language [kaz|rus]` - Filter by language (Kazakh or Russian)
- `-v, --verbose` - Show detailed output

**Examples:**

```bash
# Generate both language versions
uv run form1-parser generate-instructor-excel output/schedule.json -o output/instructors/

# Generate Kazakh version only
uv run form1-parser generate-instructor-excel output/schedule.json -l kaz

# Generate Russian version only
uv run form1-parser generate-instructor-excel output/schedule.json -l rus
```

**Output Files:**

Files are named: `instructor_schedules_{language}.xlsx`

Examples:
- `instructor_schedules_kaz.xlsx` - Kazakh version
- `instructor_schedules_rus.xlsx` - Russian version

**Sheet Layout:**
- Each sheet represents one instructor
- Rows: Monday-Friday (5 days)
- Columns: Day name + Slots 1-13 with time ranges
- Color coding: White (both weeks), Blue (odd week), Orange (even week)
- Cell content: Subject, Stream type, Groups, Room + Address

## Testing

```bash
uv run pytest tests/ -v
```

## Project Structure

```
schedule-generator-python/
├── pyproject.toml
├── src/
│   └── form1_parser/
│       ├── __init__.py
│       ├── cli.py          # CLI entry point
│       ├── parser.py       # Main Form1Parser class
│       ├── patterns.py     # Pattern detection
│       ├── extractors.py   # Stream extraction
│       ├── models.py       # Data models
│       ├── validators.py   # Validation logic
│       ├── exporters.py    # JSON/CSV/Excel export
│       ├── constants.py    # Constants and regex
│       ├── utils.py        # Helper functions
│       ├── exceptions.py   # Custom exceptions
│       └── scheduler/      # Schedule generation
│           ├── __init__.py
│           ├── algorithm.py    # Stage1Scheduler
│           ├── conflicts.py    # ConflictTracker
│           ├── rooms.py        # RoomManager
│           ├── models.py       # Schedule models
│           ├── constants.py       # Time slots, shifts
│           ├── utils.py           # Scheduling utilities
│           ├── exporter.py        # Schedule JSON export
│           ├── excel_generator.py # Excel schedule generator
│           └── instructor_excel_generator.py # Instructor schedule generator
├── tests/
│   ├── conftest.py
│   ├── test_models.py
│   ├── test_utils.py
│   ├── test_patterns.py
│   ├── test_extractors.py
│   ├── test_parser.py
│   └── scheduler/          # Scheduler tests
│       ├── test_algorithm.py
│       ├── test_conflicts.py
│       ├── test_rooms.py
│       ├── test_utils.py
│       ├── test_excel_generator.py
│       └── test_instructor_excel_generator.py
├── data/
│   ├── form-1.xlsx         # Input Form-1 file
│   └── reference/          # Reference data
│       ├── rooms.csv
│       ├── subject-rooms.json
│       ├── instructor-rooms.json
│       └── group-buildings.json
└── output/                 # Output files
```
