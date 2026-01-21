# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Form-1 Parser extracts academic workload data from Form-1 (Ф-1) Excel spreadsheets used by West Kazakhstan Innovation and Technological University. It parses department sheets to extract lecture, practical, and laboratory streams with their assigned instructors.

## Commands

```bash
# Install dependencies
uv sync

# Run CLI commands
uv run form1-parser parse data/form-1.xlsx -o output/result.json
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

### Data Flow

1. **CLI** (`cli.py`) → Entry point using Typer, handles parse/validate/stats commands
2. **Parser** (`parser.py`) → `Form1Parser` reads Excel sheets, finds data boundaries, groups by subject
3. **Pattern Detection** (`patterns.py`) → Detects which of 4 patterns a subject uses based on group repetition and hours fill rate
4. **Extractors** (`extractors.py`) → Strategy pattern with 4 extractors, one per data pattern
5. **Exporters** (`exporters.py`) → JSON/CSV/Excel output via `get_exporter(format)` factory

### Data Patterns

The parser handles 4 distinct patterns for how subjects organize their data:

- **1a** (Horizontal-Individual): Each row has its own practical/lab hours
- **1b** (Horizontal-Merged): NaN in prac/lab means merge with previous stream
- **implicit_subgroup**: Same group name repeated for lab subgroups
- **explicit_subgroup**: Groups with notation like `/1/`, `\1\`, `-1`

### Key Models (`models.py`)

- `Stream`: Single academic stream (subject + type + instructor + groups)
- `WeeklyHours`: Calculates odd/even week hours from total using formula: `total = odd×8 + even×7`
- `SubjectSummary`: Groups streams by subject with detected pattern
- `ParseResult`: Complete parse output with streams, subjects, errors, warnings

### Sheet Processing

- Sheets are processed by name (defined in `SHEET_NAMES` constant)
- Data start row found by looking for "1" or "2 семестр" markers
- Instructor column varies per sheet (hardcoded in `KNOWN_INSTRUCTOR_COLUMNS`)
- Subject names are forward-filled since they span multiple group rows
