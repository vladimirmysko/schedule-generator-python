# Schedule Excel Generator - Technical Specification

## Overview

This specification describes how to generate university schedule Excel files from JSON data using Python with `openpyxl` and `pandas` libraries, managed by `uv`.

## Source JSON Structure

### Top-Level Schema

```json
{
  "generation_date": "ISO 8601 datetime string",
  "stage": 1,
  "total_assigned": 140,
  "total_unscheduled": 1,
  "assignments": [...],
  "unscheduled_stream_ids": ["stream_id_1", ...],
  "statistics": {...}
}
```

### Assignment Object Schema

```json
{
  "stream_id": "unique_stream_identifier",
  "subject": "Subject Name",
  "instructor": "Instructor Name with Title",
  "groups": ["GROUP-11 О", "GROUP-13 О", ...],
  "student_count": 150,
  "day": "monday|tuesday|wednesday|thursday|friday|saturday",
  "slot": 1-13,
  "time": "HH:MM-HH:MM",
  "room": "Room Code",
  "room_address": "Full Address",
  "week_type": "odd|even|both"
}
```

### Day Mapping (JSON → Display)

| JSON Value | Kazakh | Russian |
|------------|--------|---------|
| monday | Дүйсенбі | Понедельник |
| tuesday | Сейсенбі | Вторник |
| wednesday | Сәрсенбі | Среда |
| thursday | Бейсенбі | Четверг |
| friday | Жұма | Пятница |
| saturday | Сенбі | Суббота |

### Time Slot Mapping

| Slot | Time | Shift |
|------|------|-------|
| 1 | 08:00-08:50 or 09:00-09:50 | 1st |
| 2 | 09:00-09:50 or 10:00-10:50 | 1st |
| 3 | 10:00-10:50 or 11:00-11:50 | 1st |
| 4 | 11:00-11:50 or 12:00-12:50 | 1st |
| 5 | 12:00-12:50 or 13:00-13:50 | 1st |
| 6 | 13:00-13:50 or 14:00-14:50 | 1st |
| 7 | 15:00-15:50 | 1st/2nd |
| 8 | 16:00-16:50 | 2nd |
| 9 | 17:00-17:50 | 2nd |
| 10 | 18:00-18:50 | 2nd |
| 11 | 19:00-19:50 | 2nd |
| 12 | 20:00-20:50 | 2nd |
| 13 | 21:00-21:50 | 2nd |

**Note:** First shift uses slots 1-7, second shift uses slots 7-13. The exact start time depends on the shift configuration.

---

## Output File Naming Convention

```
schedule_{language}_{year}_{week_type}.xlsx
```

| Parameter | Values | Description |
|-----------|--------|-------------|
| `language` | `kaz`, `rus` | Kazakh or Russian language variant |
| `year` | `1y`, `2y`, `3y`, `4y` | Student year (курс) |
| `week_type` | `odd`, `even` | Нечетная/четная or Тақ/жұп week |

**Examples:**
- `schedule_kaz_1y_odd.xlsx` - Kazakh, 1st year, odd weeks
- `schedule_rus_2y_even.xlsx` - Russian, 2nd year, even weeks

---

## Group Classification

### Year Detection

Extract year from group code pattern: `PREFIX-XY О`
- `X` = year digit (1, 2, 3, 4)
- `Y` = group number within year
- Example: `АРХ-21 О` → Year 2, `ЮР-11 О` → Year 1

```python
import re
def get_year_from_group(group: str) -> int:
    match = re.search(r'-(\d)', group)
    return int(match.group(1)) if match else 0
```

### Language Detection

- Default: Kazakh (`kaz`)
- Russian markers: Groups containing `/г/` or `/р/` → Russian (`rus`)
- Example: `ЮР-22 О /г/` → Russian language group

```python
def is_russian_group(group: str) -> bool:
    return '/г/' in group or '/р/' in group
```

---

## Excel File Structure

### Sheet Organization

Each workbook contains multiple sheets, with **3 groups per sheet** (maximum).

**Sheet naming:** Comma-separated group names
```
АРХ-11 О, АРХ-11А О, АРХ-13 О
```

### Layout Structure (47 rows × 6 columns)

| Row | A | B | C | D | E | F |
|-----|---|---|---|---|---|---|
| 1 | (empty) | | | | | |
| 2 | University Name (merged A2:F2) | | | | | |
| 3 | | | | | | Approval Text |
| 4 | | | | | | Position |
| 5 | | | | | | Date Line |
| 6 | Schedule Title (merged A6:F6) | | | | | |
| 7 | Date Range | | | | | |
| 8 | Course/Year (merged A8:F8) | | | | | |
| 9 | Day Header | Time Header | № | Group 1 | Group 2 | Group 3 |
| 10-16 | Monday Block | Time Slots | 1-7 | Classes | Classes | Classes |
| 17-23 | Tuesday Block | Time Slots | 1-7 | Classes | Classes | Classes |
| 24-30 | Wednesday Block | Time Slots | 1-7 | Classes | Classes | Classes |
| 31-37 | Thursday Block | Time Slots | 1-7 | Classes | Classes | Classes |
| 38-44 | Friday Block | Time Slots | 1-7 | Classes | Classes | Classes |
| 45 | (empty) | | | | | |
| 46 | Agreement Text (merged A46:C46) | | | | | |
| 47 | Date Line (merged A47:C47) | | | | | |

### Day Row Ranges

| Day | Start Row | End Row | Merged Cells |
|-----|-----------|---------|--------------|
| Monday | 10 | 16 | A10:A16 |
| Tuesday | 17 | 23 | A17:A23 |
| Wednesday | 24 | 30 | A24:A30 |
| Thursday | 31 | 37 | A31:A37 |
| Friday | 38 | 44 | A38:A44 |

### Merged Cell Ranges

```python
MERGED_CELLS = [
    'A2:F2',   # University name
    'A6:F6',   # Schedule title
    'A8:F8',   # Course/year
    'A10:A16', # Monday label
    'A17:A23', # Tuesday label
    'A24:A30', # Wednesday label
    'A31:A37', # Thursday label
    'A38:A44', # Friday label
    'A46:C46', # Agreement text
    'A47:C47', # Date line
]
```

---

## Column Specifications

| Column | Width | Content |
|--------|-------|---------|
| A | 12.0 | Day name (merged for each day) |
| B | 14.0 | Time slot (e.g., "08:00-08:50") |
| C | 5.0 | Slot number (1-7 or 7-13) |
| D | 30.0 | Group 1 schedule cell |
| E | 13.0 | Group 2 schedule cell |
| F | 13.0 | Group 3 schedule cell |

### Row Heights

| Rows | Height |
|------|--------|
| 1-8 | Default (None) |
| 9 | 30.0 |
| 10-44 | 55.0 |
| 45-47 | Default |

---

## Cell Content Format

### Schedule Cell Content

```
SUBJECT NAME (UPPERCASE)
Instructor Name
Room, Address
```

**Format:** `\n` (newline) separated, 3 lines per class

```python
def format_cell_content(assignment: dict) -> str:
    subject = assignment['subject'].upper()
    instructor = assignment['instructor'].replace('а.о.', '').replace('қ.проф.', '')
    room_info = f"{assignment['room']}, {assignment['room_address']}"
    return f"{subject}\n{instructor}\n{room_info}"
```

### Empty Cells

Leave `None` for time slots without classes.

---

## Font Specifications

### Font Family
All cells use **Times New Roman**

### Font Sizes by Cell Type

| Cell Type | Size | Bold |
|-----------|------|------|
| University name (A2) | 16 | Yes |
| Schedule title (A6) | 16 | Yes |
| Course/year (A8) | 16 | Yes |
| Column headers (Row 9, A-C) | 12 | Yes |
| Group names (Row 9, D-F) | 14 | Yes |
| Day names (Column A) | 11 | Yes |
| Time slots (Column B) | 10 | No |
| Schedule content (D-F) | 11 | No |
| Approval text (F3-F5) | 11 | No |

---

## Alignment Specifications

| Cell Type | Horizontal | Vertical | Wrap Text |
|-----------|------------|----------|-----------|
| Headers | center | center | Yes |
| Day names | center | center | Yes |
| Time slots | center | center | Yes |
| Schedule cells | center | center | Yes |
| Approval text (F3-F5) | right | center | No |

---

## Border Specifications

### Table Area (Rows 9-44, Columns A-F)

All cells within the schedule table have **thin borders** on all sides:
- Top: thin
- Bottom: thin
- Left: thin
- Right: thin

### Outside Table

No borders (header rows 1-8, footer rows 45-47)

---

## Localization Strings

### Kazakh Language (`kaz`)

```python
STRINGS_KAZ = {
    'university': 'Батыс Қазақстан инновациялық-технологиялық университеті',
    'schedule_title': 'САБАҚ КЕСТЕСІ',
    'approval': 'Бекітемін',
    'position': 'ОЖ бойынша проректор м.а. ______________',
    'date_line': '"___" _____________ 2025 ж.',
    'agreement': 'Келісілді СТИ директоры ______________',
    'day_header': 'Күн',
    'time_header': 'Уақыт',
    'course_template': '{} курс',  # e.g., "1 курс"
    'days': {
        'monday': 'Дүйсенбі',
        'tuesday': 'Сейсенбі',
        'wednesday': 'Сәрсенбі',
        'thursday': 'Бейсенбі',
        'friday': 'Жұма',
        'saturday': 'Сенбі'
    }
}
```

### Russian Language (`rus`)

```python
STRINGS_RUS = {
    'university': 'Западно-Казахстанский инновационно-технологический университет',
    'schedule_title': 'РАСПИСАНИЕ ЗАНЯТИЙ',
    'approval': 'Утверждаю',
    'position': 'и.о. проректора по УР ______________',
    'date_line': '"___" _____________ 2025 г.',
    'agreement': 'Согласовано директор СТИ ______________',
    'day_header': 'День',
    'time_header': 'Время',
    'course_template': '{} курс',  # e.g., "2 курс"
    'days': {
        'monday': 'Понедельник',
        'tuesday': 'Вторник',
        'wednesday': 'Среда',
        'thursday': 'Четверг',
        'friday': 'Пятница',
        'saturday': 'Суббота'
    }
}
```

---

## Week Type Filtering

Filter assignments by `week_type` field:

```python
def filter_by_week_type(assignments: list, target_week: str) -> list:
    """
    Filter assignments for specific week type.
    
    Args:
        assignments: List of assignment dicts
        target_week: 'odd' or 'even'
    
    Returns:
        Assignments for target week (includes 'both' type)
    """
    return [
        a for a in assignments 
        if a['week_type'] == target_week or a['week_type'] == 'both'
    ]
```

---

## Date Range Header

Row 7 contains the date range string. Example format:
```
19-23/01, 26-30/01, 02-06/02, 09-13/02, 16-20/02
```

This should be generated based on:
- Week type (odd/even)
- Academic calendar configuration

---

## Algorithm: Group Assignment to Sheets

```python
def group_into_sheets(groups: list[str], max_per_sheet: int = 3) -> list[list[str]]:
    """Split groups into sheets with max 3 groups each."""
    sheets = []
    for i in range(0, len(groups), max_per_sheet):
        sheets.append(groups[i:i + max_per_sheet])
    return sheets

def get_sheet_name(groups: list[str]) -> str:
    """Generate sheet name from group list."""
    return ', '.join(groups)
```

---

## Algorithm: Build Schedule Grid

```python
def build_schedule_grid(assignments: list, groups: list[str]) -> dict:
    """
    Build 2D schedule grid for given groups.
    
    Returns:
        dict[day][slot][group] = assignment or None
    """
    grid = {}
    days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
    
    for day in days:
        grid[day] = {}
        for slot in range(1, 8):  # or 7-14 for second shift
            grid[day][slot] = {group: None for group in groups}
    
    for assignment in assignments:
        day = assignment['day']
        slot = assignment['slot']
        for group in assignment['groups']:
            if group in groups:
                if day in grid and slot in grid[day]:
                    grid[day][slot][group] = assignment
    
    return grid
```

---

## Project Setup with `uv`

### pyproject.toml

```toml
[project]
name = "schedule-generator"
version = "0.1.0"
description = "University schedule Excel generator from JSON"
requires-python = ">=3.10"
dependencies = [
    "openpyxl>=3.1.0",
    "pandas>=2.0.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### Installation

```bash
# Initialize project
uv init schedule-generator
cd schedule-generator

# Add dependencies
uv add openpyxl pandas

# Run generator
uv run python generate_schedule.py input.json output_dir/
```

---

## Implementation Skeleton

```python
#!/usr/bin/env python3
"""
Schedule Excel Generator
Generates university schedule Excel files from JSON data.
"""

import json
import re
from pathlib import Path
from dataclasses import dataclass
from typing import Literal

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter


@dataclass
class GeneratorConfig:
    language: Literal['kaz', 'rus']
    year: int
    week_type: Literal['odd', 'even']
    first_slot: int = 1  # Starting slot number
    slots_per_day: int = 7  # Number of slots to show


class ScheduleGenerator:
    def __init__(self, config: GeneratorConfig):
        self.config = config
        self.strings = STRINGS_KAZ if config.language == 'kaz' else STRINGS_RUS
    
    def load_json(self, path: Path) -> dict:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def filter_assignments(self, data: dict) -> list:
        assignments = data['assignments']
        
        # Filter by week type
        assignments = [
            a for a in assignments
            if a['week_type'] in (self.config.week_type, 'both')
        ]
        
        # Filter by year
        year_groups = set()
        for a in assignments:
            for g in a['groups']:
                if self.get_year_from_group(g) == self.config.year:
                    year_groups.add(g)
        
        # Filter by language
        if self.config.language == 'rus':
            year_groups = {g for g in year_groups if self.is_russian_group(g)}
        else:
            year_groups = {g for g in year_groups if not self.is_russian_group(g)}
        
        return assignments, sorted(year_groups)
    
    @staticmethod
    def get_year_from_group(group: str) -> int:
        match = re.search(r'-(\d)', group)
        return int(match.group(1)) if match else 0
    
    @staticmethod
    def is_russian_group(group: str) -> bool:
        return '/г/' in group or '/р/' in group
    
    def create_workbook(self, assignments: list, groups: list) -> Workbook:
        wb = Workbook()
        wb.remove(wb.active)
        
        # Split groups into sheets (max 3 per sheet)
        sheets = [groups[i:i+3] for i in range(0, len(groups), 3)]
        
        for sheet_groups in sheets:
            ws = wb.create_sheet(title=', '.join(sheet_groups)[:31])
            self.setup_sheet(ws, sheet_groups)
            self.fill_schedule(ws, assignments, sheet_groups)
        
        return wb
    
    def setup_sheet(self, ws, groups: list):
        # Set column widths
        ws.column_dimensions['A'].width = 12.0
        ws.column_dimensions['B'].width = 14.0
        ws.column_dimensions['C'].width = 5.0
        ws.column_dimensions['D'].width = 30.0
        ws.column_dimensions['E'].width = 13.0
        ws.column_dimensions['F'].width = 13.0
        
        # Setup header rows
        self.setup_headers(ws, groups)
        
        # Setup schedule grid
        self.setup_grid(ws)
    
    def setup_headers(self, ws, groups: list):
        # Implementation: set up rows 1-9 with headers
        pass
    
    def setup_grid(self, ws):
        # Implementation: set up rows 10-44 with days/times
        pass
    
    def fill_schedule(self, ws, assignments: list, groups: list):
        # Implementation: fill in schedule data
        pass
    
    def save(self, wb: Workbook, output_path: Path):
        wb.save(output_path)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate schedule Excel files')
    parser.add_argument('input', type=Path, help='Input JSON file')
    parser.add_argument('output_dir', type=Path, help='Output directory')
    parser.add_argument('--language', choices=['kaz', 'rus'], default='kaz')
    parser.add_argument('--year', type=int, required=True)
    parser.add_argument('--week-type', choices=['odd', 'even'], required=True)
    
    args = parser.parse_args()
    
    config = GeneratorConfig(
        language=args.language,
        year=args.year,
        week_type=args.week_type
    )
    
    generator = ScheduleGenerator(config)
    data = generator.load_json(args.input)
    assignments, groups = generator.filter_assignments(data)
    wb = generator.create_workbook(assignments, groups)
    
    output_file = args.output_dir / f'schedule_{args.language}_{args.year}y_{args.week_type}.xlsx'
    generator.save(wb, output_file)
    print(f'Generated: {output_file}')


if __name__ == '__main__':
    main()
```

---

## Appendix: Complete Style Objects

```python
from openpyxl.styles import Font, Alignment, Border, Side

# Fonts
FONT_TITLE = Font(name='Times New Roman', size=16, bold=True)
FONT_HEADER = Font(name='Times New Roman', size=12, bold=True)
FONT_GROUP = Font(name='Times New Roman', size=14, bold=True)
FONT_DAY = Font(name='Times New Roman', size=11, bold=True)
FONT_TIME = Font(name='Times New Roman', size=10, bold=False)
FONT_CELL = Font(name='Times New Roman', size=11, bold=False)
FONT_APPROVAL = Font(name='Times New Roman', size=11, bold=False)

# Alignments
ALIGN_CENTER = Alignment(horizontal='center', vertical='center', wrap_text=True)
ALIGN_CENTER_NOWRAP = Alignment(horizontal='center', vertical='center', wrap_text=False)
ALIGN_RIGHT = Alignment(horizontal='right', vertical='center', wrap_text=False)

# Borders
THIN_BORDER = Border(
    left=Side(style='thin'),
    right=Side(style='thin'),
    top=Side(style='thin'),
    bottom=Side(style='thin')
)
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01 | Initial specification |