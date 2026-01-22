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
│       └── exceptions.py   # Custom exceptions
├── tests/
│   ├── conftest.py
│   ├── test_models.py
│   ├── test_utils.py
│   ├── test_patterns.py
│   ├── test_extractors.py
│   └── test_parser.py
├── data/
│   ├── form-1.xlsx         # Input Form-1 file
│   └── reference/          # Reference data
│       ├── rooms.csv
│       ├── subject-rooms.json
│       ├── instructor-rooms.json
│       └── group-buildings.json
└── output/                 # Output files
```
