# Form-1 Parser Specification
## University Schedule Stream Analysis Tool

**Version:** 1.1
**Date:** January 2026
**Target:** Claude Code Implementation

---

## 1. Project Overview

### 1.1 Purpose
Parse Form-1 (Ф-1) Excel workload spreadsheets from West Kazakhstan Innovation and Technological University to identify and extract lecture, practical, and laboratory streams with their assigned instructors.

### 1.2 Tech Stack
```
Python 3.13+
Package Manager: uv
Dependencies:
  - openpyxl
  - pandas
```

### 1.3 Installation
```bash
uv init form1-parser
cd form1-parser
uv add openpyxl pandas
```

---

## 2. Input File Structure

### 2.1 File Format
- **Type:** Excel workbook (.xlsx)
- **Sheets:** 7 department sheets
  - `оод (2)` - General education
  - `эиб` - Economics and business
  - `юр` - Law
  - `стр` - Construction
  - `эл` - Electrical
  - `ттт` - Transport
  - `нд` - Oil and gas

### 2.2 Column Structure
| Index | Column Name (KZ) | Description | Required |
|-------|------------------|-------------|----------|
| 0 | № | Row number / Semester marker | No |
| 1 | Пән атауы | Subject name | Yes |
| 2 | (varies) | Room/building info | No |
| 3 | Мамандық шифры | Specialty code (e.g., 6В07302) | Yes |
| 4 | Курс, топ атауы | Group name (e.g., СТР-21 О) | Yes |
| 5 | Жоспарланған кредит саны | Planned credits | No |
| 6 | Оқу тілі | Language (каз/орыс) | Yes |
| 7 | Студенттер саны | Student count | Yes |
| 8 | Дәрістер | Lecture hours | Yes |
| 9 | Практикалық | Practical hours | Yes |
| 10 | Зертханалық | Laboratory hours | Yes |
| **LAST** | (varies) | **Instructor name** | Yes |

### 2.3 Data Start Detection
- Find row where column 0 contains `"1"` or `"2 семестр"` or `"2семестр"`
- Skip semester header row if present
- Data rows follow immediately after

### 2.4 Subject Name Forward-Fill
Subject names appear only in the first row of each subject block. Subsequent rows have empty/NaN values. Apply forward-fill to propagate subject names.

---

## 3. Core Concept: Stream Definition

### 3.1 Fundamental Rule
```
ONE STREAM = ONE INSTRUCTOR
```

A stream is uniquely identified by:
- **Subject** (Пән атауы)
- **Class Type** (Lecture / Practical / Lab)
- **Instructor** (last column)

**If different instructor → DIFFERENT stream (always!)**

### 3.2 Stream Types
| Type | Kazakh | Description |
|------|--------|-------------|
| Lecture | Дәрістер | Combined groups, theoretical instruction |
| Practical | Практикалық | Smaller groups, applied exercises |
| Laboratory | Зертханалық | Smallest groups, hands-on lab work |

---

## 4. Data Entry Patterns

The spreadsheet uses multiple data entry patterns. The parser must detect and handle each correctly.

### 4.1 Pattern 1a: Horizontal - Individual
**Characteristics:**
- Each group appears ONCE per subject
- Each row has its own Practical/Lab hours
- Most rows have values in Prac/Lab columns

**Detection:** `group_count == 1` AND `prac_fill_rate > 0.5`

**Example:**
```
Row | Group    | Lec | Prac | Lab | Instructor
----|----------|-----|------|-----|------------
1   | ВЕТ-31 О | 15  |  23  |  7  | Instructor A
2   | ВЕТ-32 О | 15  |  23  |  7  | Instructor B
```

**Stream Rules:**
- Lecture: Each row with Lec > 0 where instructor differs = separate stream
- Practical: Each row with Prac > 0 = 1 stream
- Lab: Each row with Lab > 0 = 1 stream

---

### 4.2 Pattern 1b: Horizontal - Merged (Chemistry-style)
**Characteristics:**
- Each group appears ONCE per subject
- NaN in Prac/Lab means "merged with previous group's stream"
- Periodic rows have hours, others have NaN

**Detection:** `group_count == 1` AND `prac_fill_rate <= 0.5`

**Example:**
```
Row | Group     | Lec | Prac | Lab | Instructor
----|-----------|-----|------|-----|------------
1   | БЖД-11 О  | 30  |   8  |  7  | Instructor A  ← Stream leader
2   | ВЕТ-11 О  |  -  |   -  |  -  | Instructor A  ← Merged
3   | ТБПП-11 О |  -  |   8  |  7  | Instructor A  ← New stream leader
4   | ЗК-11 О   |  -  |   -  |  -  | Instructor A  ← Merged
```

**Stream Rules:**
- Lecture: Unique instructors with Lec > 0
- Practical: Row with hours starts new stream; following NaN rows merge into it
- Lab: Same as practical

---

### 4.3 Implicit Subgroups (Same Group Repeated for Labs)
**Characteristics:**
- Same group name appears multiple times WITHOUT explicit subgroup notation
- Typically used for lab sessions (equipment/space constraints)
- First row has full info, subsequent rows have only Lab hours

**Detection:** `max(group_counts) > 1` for regular group names

**Example:**
```
Row | Group    | Lec | Prac | Lab | Instructor
----|----------|-----|------|-----|------------
11  | СТР-21 О | 30  |   8  |  7  | Instructor A  ← Full info + Lab subgroup 1
12  | СТР-21 О |  -  |   -  |  7  | Instructor A  ← Lab subgroup 2 only
```

**Stream Rules:**
- Lecture: Unique instructors with Lec > 0
- Practical: FIRST occurrence per group with Prac > 0
- Lab: EVERY row with Lab > 0 (each is separate stream)

---

### 4.4 Explicit Subgroups (Marked Notation)
**Characteristics:**
- Group names contain explicit subgroup markers
- Each subgroup row = separate stream

**Notation Patterns:**
| Pattern | Regex | Example |
|---------|-------|---------|
| Forward slash | `/[12]/` | `АРХ-11 О /1/` |
| Backslash | `\\[12]\\` | `АРХ-11 О \1\` |
| Dash | `\s-[12]$` | `АРХ-15 О -1` |

**Detection Regex:**
```python
EXPLICIT_SUBGROUP_PATTERN = r'/[12]/|\\[12]\\|\s-[12]$'
```

**Example:**
```
Row | Group         | Prac | Instructor
----|---------------|------|------------
1   | АРХ-11 О /1/  |  45  | Instructor A
2   | АРХ-11 О /2/  |  45  | Instructor A
```

**Stream Rules:**
- Each subgroup row with hours = 1 stream

---

### 4.5 Study Form Indicators (NOT Subgroups)
**Characteristics:**
- Notation indicates study program type, NOT subgroups
- Treat as completely separate, independent groups

**Notation:**
| Pattern | Meaning |
|---------|---------|
| `/у/` | Ускоренное (accelerated program) |
| `/г/` | Грантовое (state-funded program) |

**Detection Regex:**
```python
STUDY_FORM_PATTERN = r'/[уг]/'
```

**Rule:** Treat these as regular groups. Do NOT extract base group.

---

## 5. Instructor Column Detection

### 5.1 Rule
Always use the **LAST (rightmost)** column containing instructor names.

### 5.2 Detection Algorithm
Two-step approach: first check known positions, then fall back to marker scan.

```python
def find_instructor_column(df: pd.DataFrame, sheet_name: str) -> int:
    """Find the rightmost column with instructor names.

    Args:
        df: DataFrame of the sheet
        sheet_name: Name of the sheet

    Returns:
        Column index of the instructor column

    Raises:
        InstructorColumnNotFoundError: If instructor column cannot be found
    """
    # Step 1: Check known column positions first
    if sheet_name in KNOWN_INSTRUCTOR_COLUMNS:
        known_col = KNOWN_INSTRUCTOR_COLUMNS[sheet_name]
        if known_col < len(df.columns):
            return known_col

    # Step 2: Search from right to left for instructor markers
    for col in range(len(df.columns) - 1, -1, -1):
        for row in range(11, min(50, len(df))):
            if row >= len(df):
                break
            val = str(df.iloc[row, col]).lower() if pd.notna(df.iloc[row, col]) else ''
            if any(marker in val for marker in INSTRUCTOR_MARKERS):
                return col

    raise InstructorColumnNotFoundError(sheet_name)
```

### 5.3 Known Column Positions
| Sheet | Instructor Column |
|-------|------------------|
| оод (2) | 25 |
| эиб | 25 |
| юр | 25 |
| стр | 26 |
| эл | 25 |
| ттт | 25 |
| нд | 26 |

---

## 6. Academic Week Structure & Hours Calculation

### 6.1 Semester Structure
```
Total: 15 academic weeks
  - 8 ODD weeks:  1, 3, 5, 7, 9, 11, 13, 15
  - 7 EVEN weeks: 2, 4, 6, 8, 10, 12, 14
```

### 6.2 Hours Formula
The spreadsheet contains **total semester hours**. To calculate weekly hours:

```
total_hours = (odd_week_hours × 8) + (even_week_hours × 7)
```

### 6.3 Hours Conversion Table
| Total Hours | Odd Week (hrs) | Even Week (hrs) | Verification |
|-------------|----------------|-----------------|--------------|
| 7 | 0 | 1 | 0×8 + 1×7 = 7 |
| 8 | 1 | 0 | 1×8 + 0×7 = 8 |
| 15 | 1 | 1 | 1×8 + 1×7 = 15 |
| 22 | 1 | 2 | 1×8 + 2×7 = 22 |
| 23 | 2 | 1 | 2×8 + 1×7 = 23 |
| 30 | 2 | 2 | 2×8 + 2×7 = 30 |
| 37 | 2 | 3 | 2×8 + 3×7 = 37 |
| 38 | 3 | 2 | 3×8 + 2×7 = 38 |
| 45 | 3 | 3 | 3×8 + 3×7 = 45 |

### 6.4 Calculation Algorithm
```python
def calculate_weekly_hours(total_hours: int) -> tuple[int, int]:
    """
    Calculate hours per odd and even week from total semester hours.
    
    Args:
        total_hours: Total semester hours from spreadsheet
        
    Returns:
        (odd_week_hours, even_week_hours)
        
    Raises:
        ValueError: If total_hours doesn't fit the formula
    """
    remainder = total_hours % 15
    base = total_hours // 15
    
    if remainder == 0:
        return (base, base)           # Equal hours both weeks
    elif remainder == 8:
        return (base + 1, base)       # Odd week has 1 more hour
    elif remainder == 7:
        return (base, base + 1)       # Even week has 1 more hour
    else:
        raise ValueError(
            f"Invalid total hours: {total_hours}. "
            f"Must satisfy: 8×odd + 7×even = total"
        )
```

### 6.5 Practical Implications
- **7 hours (Labs):** Only on EVEN weeks (1 hr/week)
- **8 hours (Practicals):** Only on ODD weeks (1 hr/week)
- **15 hours:** Every week (1 hr/week)
- **30 hours:** Every week (2 hrs/week)
- **38 hours:** 3 hrs on odd weeks, 2 hrs on even weeks

---

## 7. Output Data Structures

### 7.1 Stream Model
```python
from dataclasses import dataclass, field
from typing import List, Optional, Self
from enum import Enum

from .exceptions import InvalidHoursError

class StreamType(Enum):
    LECTURE = "lecture"
    PRACTICAL = "practical"
    LAB = "lab"

@dataclass
class WeeklyHours:
    """Hours per week for scheduling."""
    total: int                       # Total semester hours (from spreadsheet)
    odd_week: int                    # Hours on odd weeks (1,3,5,7,9,11,13,15)
    even_week: int                   # Hours on even weeks (2,4,6,8,10,12,14)

    @classmethod
    def from_total(cls, total_hours: int) -> Self:
        """Calculate weekly hours from total semester hours."""
        if total_hours == 0:
            return cls(total=0, odd_week=0, even_week=0)

        remainder = total_hours % 15
        base = total_hours // 15

        if remainder == 0:
            return cls(total=total_hours, odd_week=base, even_week=base)
        elif remainder == 8:
            return cls(total=total_hours, odd_week=base + 1, even_week=base)
        elif remainder == 7:
            return cls(total=total_hours, odd_week=base, even_week=base + 1)
        else:
            raise InvalidHoursError(total_hours)

    def __str__(self) -> str:
        return f"{self.total}h (odd:{self.odd_week}, even:{self.even_week})"

@dataclass
class Stream:
    id: str                          # Unique identifier
    subject: str                     # Subject name
    stream_type: StreamType          # lecture/practical/lab
    instructor: str                  # Instructor name (from last column)
    language: str                    # каз or орыс
    hours: WeeklyHours               # Hours breakdown (total + per week)
    groups: List[str]                # List of group names in this stream
    student_count: int               # Total students in stream
    sheet: str                       # Source sheet name
    rows: List[int]                  # Source row numbers
    is_subgroup: bool = False        # True if explicit subgroup notation
    is_implicit_subgroup: bool = False  # True if implicit subgroup (repeated group)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "subject": self.subject,
            "stream_type": self.stream_type.value,
            "instructor": self.instructor,
            "language": self.language,
            "hours": {
                "total": self.hours.total,
                "odd_week": self.hours.odd_week,
                "even_week": self.hours.even_week,
            },
            "groups": self.groups,
            "student_count": self.student_count,
            "sheet": self.sheet,
            "rows": self.rows,
            "is_subgroup": self.is_subgroup,
            "is_implicit_subgroup": self.is_implicit_subgroup,
        }
```

### 7.2 Subject Summary
```python
@dataclass
class SubjectSummary:
    subject: str
    sheet: str
    pattern: str                     # "1a", "1b", "implicit_subgroup", "explicit_subgroup"
    lecture_streams: List[Stream] = field(default_factory=list)
    practical_streams: List[Stream] = field(default_factory=list)
    lab_streams: List[Stream] = field(default_factory=list)

    @property
    def total_streams(self) -> int:
        """Total number of streams for this subject."""
        return len(self.lecture_streams) + len(self.practical_streams) + len(self.lab_streams)

    @property
    def total_hours(self) -> int:
        """Total hours across all streams."""
        total = 0
        for stream in self.lecture_streams + self.practical_streams + self.lab_streams:
            total += stream.hours.total
        return total

    @property
    def instructors(self) -> List[str]:
        """List of unique instructors for this subject."""
        instructors = set()
        for stream in self.lecture_streams + self.practical_streams + self.lab_streams:
            instructors.add(stream.instructor)
        return sorted(instructors)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "subject": self.subject,
            "sheet": self.sheet,
            "pattern": self.pattern,
            "total_streams": self.total_streams,
            "total_hours": self.total_hours,
            "instructors": self.instructors,
            "lecture_streams": [s.to_dict() for s in self.lecture_streams],
            "practical_streams": [s.to_dict() for s in self.practical_streams],
            "lab_streams": [s.to_dict() for s in self.lab_streams],
        }
```

### 7.3 Parser Output
```python
@dataclass
class ParseResult:
    file_path: str
    parse_date: str
    sheets_processed: List[str] = field(default_factory=list)
    subjects: List[SubjectSummary] = field(default_factory=list)
    streams: List[Stream] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def total_subjects(self) -> int:
        """Total number of unique subjects."""
        return len(self.subjects)

    @property
    def total_streams(self) -> int:
        """Total number of streams."""
        return len(self.streams)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "file_path": self.file_path,
            "parse_date": self.parse_date,
            "sheets_processed": self.sheets_processed,
            "total_subjects": self.total_subjects,
            "total_streams": self.total_streams,
            "subjects": [s.to_dict() for s in self.subjects],
            "streams": [s.to_dict() for s in self.streams],
            "errors": self.errors,
            "warnings": self.warnings,
        }
```

---

## 8. Algorithm Specification

### 8.1 Main Parser Flow
```
1. Load Excel file
2. For each sheet:
   a. Detect data start row
   b. Find instructor column (check known positions, then scan for markers)
   c. Extract raw data with forward-filled subject names
   d. Group rows by subject
   e. For each subject:
      i.   Detect pattern (1a, 1b, implicit_subgroup, explicit_subgroup)
      ii.  Apply pattern-specific stream extraction
      iii. Create Stream objects
3. Aggregate results
4. Return ParseResult
```

### 8.2 Pattern Detection Algorithm
```python
def detect_pattern(subject_data: pd.DataFrame, group_col: str, practical_col: str) -> str:
    """
    Detect which data entry pattern a subject uses.

    Algorithm:
    1. Has explicit subgroup notation? → "explicit_subgroup"
    2. Same group appears multiple times? → "implicit_subgroup"
    3. Practical fill rate > 0.5? → "1a" (individual)
    4. Otherwise → "1b" (merged)

    Returns: "1a", "1b", "implicit_subgroup", or "explicit_subgroup"
    """
    groups = subject_data[group_col].dropna()

    if groups.empty:
        return "1a"  # Default to simplest pattern

    # Check for explicit subgroups first
    if groups.str.contains(EXPLICIT_SUBGROUP_PATTERN, regex=True, na=False).any():
        return "explicit_subgroup"

    # Check for implicit subgroups (same group repeated)
    group_counts = groups.value_counts()
    if group_counts.max() > 1:
        return "implicit_subgroup"

    # Check practical fill rate for 1a vs 1b
    practical_values = subject_data[practical_col]
    filled = practical_values.apply(lambda x: pd.notna(x) and float(x) > 0 if pd.notna(x) else False)
    fill_rate = filled.mean()

    if fill_rate > 0.5:
        return "1a"  # Most rows have practical hours
    else:
        return "1b"  # Merged practicals
```

### 8.3 Stream Extraction by Pattern

#### Pattern 1a (Horizontal - Individual)
```python
def extract_streams_1a(subject_data, subject_name, sheet):
    streams = []
    
    # Lecture streams: unique instructors with Lec > 0
    lecture_data = subject_data[subject_data['Lectures'] > 0]
    for instructor in lecture_data['Instructor'].unique():
        instr_data = lecture_data[lecture_data['Instructor'] == instructor]
        streams.append(Stream(
            stream_type=StreamType.LECTURE,
            instructor=instructor,
            groups=list(instr_data['Group']),
            hours=instr_data['Lectures'].iloc[0],
            ...
        ))
    
    # Practical streams: each row with Prac > 0
    for _, row in subject_data[subject_data['Practicals'] > 0].iterrows():
        streams.append(Stream(
            stream_type=StreamType.PRACTICAL,
            instructor=row['Instructor'],
            groups=[row['Group']],
            hours=row['Practicals'],
            ...
        ))
    
    # Lab streams: each row with Lab > 0
    for _, row in subject_data[subject_data['Labs'] > 0].iterrows():
        streams.append(Stream(
            stream_type=StreamType.LAB,
            instructor=row['Instructor'],
            groups=[row['Group']],
            hours=row['Labs'],
            ...
        ))
    
    return streams
```

#### Pattern 1b (Horizontal - Merged)
```python
def extract_streams_1b(subject_data, subject_name, sheet):
    streams = []
    
    # Lecture streams: unique instructors with Lec > 0
    # (same as 1a)
    
    # Practical streams: sequential merge
    current_stream_groups = []
    current_instructor = None
    current_hours = 0
    
    for _, row in subject_data.iterrows():
        if pd.notna(row['Practicals']) and row['Practicals'] > 0:
            # Save previous stream if exists
            if current_stream_groups:
                streams.append(Stream(
                    stream_type=StreamType.PRACTICAL,
                    instructor=current_instructor,
                    groups=current_stream_groups,
                    hours=current_hours,
                    ...
                ))
            # Start new stream
            current_stream_groups = [row['Group']]
            current_instructor = row['Instructor']
            current_hours = row['Practicals']
        else:
            # Merge into current stream
            if current_stream_groups:
                current_stream_groups.append(row['Group'])
    
    # Don't forget last stream
    if current_stream_groups:
        streams.append(Stream(...))
    
    # Lab streams: same logic as practical
    
    return streams
```

#### Implicit Subgroups
```python
def extract_streams_implicit_subgroup(subject_data, subject_name, sheet):
    streams = []
    
    # Lecture streams: unique instructors with Lec > 0
    # (same as 1a)
    
    # Practical streams: FIRST occurrence per group
    seen_groups = set()
    for _, row in subject_data.iterrows():
        if row['Practicals'] > 0 and row['Group'] not in seen_groups:
            streams.append(Stream(
                stream_type=StreamType.PRACTICAL,
                ...
            ))
            seen_groups.add(row['Group'])
    
    # Lab streams: EVERY row with Lab > 0
    for _, row in subject_data.iterrows():
        if row['Labs'] > 0:
            streams.append(Stream(
                stream_type=StreamType.LAB,
                is_implicit_subgroup=True,
                ...
            ))
    
    return streams
```

---

## 9. Validation Rules

### 9.1 Required Fields
- Subject name must not be empty
- Group name must be valid (length > 2)
- Language must be "каз" or "орыс"
- Instructor must not be empty for rows with hours
- At least one of Lec/Prac/Lab must be > 0

### 9.2 Data Quality Warnings
- Student count is 0 or missing
- Hours value seems unusually high (> 100)
- Duplicate stream detected
- Instructor name format doesn't match expected pattern

### 9.3 Group Name Validation
```python
GROUP_NAME_PATTERN = r'^[А-ЯӘҒҚҢӨҰҮІа-яәғқңөұүі]+-\d{2}[А-Яа-я]?\s*О?'
```

---

## 10. Error Handling

### 10.1 Error Types
```python
class ParseError(Exception):
    """Base exception for parser errors."""
    pass

class SheetNotFoundError(ParseError):
    """Sheet not found in workbook."""
    pass

class DataStartNotFoundError(ParseError):
    """Could not locate data start row."""
    pass

class InstructorColumnNotFoundError(ParseError):
    """Could not locate instructor column."""
    pass

class InvalidDataError(ParseError):
    """Data validation failed."""
    pass

class InvalidHoursError(ParseError):
    """Hours value doesn't satisfy formula: 8×odd + 7×even = total."""
    pass
```

### 10.2 Error Recovery
- If one sheet fails, continue processing others
- Log all errors and warnings
- Return partial results with error list

---

## 11. CLI Interface

### 11.1 Commands
```bash
# Parse single file
uv run form1-parser parse input.xlsx -o output.json

# Parse with verbose output
uv run form1-parser parse input.xlsx -v

# Validate file structure only
uv run form1-parser validate input.xlsx

# Export to different formats
uv run form1-parser parse input.xlsx --format csv --output-dir ./results/

# Show statistics
uv run form1-parser stats input.xlsx
```

### 11.2 Output Formats
- JSON (default)
- CSV (multiple files: streams.csv, subjects.csv, summary.csv)
- Excel (single workbook with multiple sheets)

---

## 12. Testing Requirements

### 12.1 Unit Tests
- Pattern detection for each pattern type
- Stream extraction for each pattern
- Instructor column detection
- Group name validation
- Subgroup notation parsing

### 12.2 Integration Tests
- Full file parsing
- Multi-sheet processing
- Error handling and recovery

### 12.3 Test Data
- Provide sample Excel file with all pattern types
- Include edge cases (empty rows, missing data, unusual values)

---

## 13. File Structure

```
form1-parser/
├── pyproject.toml
├── README.md
├── src/
│   └── form1_parser/
│       ├── __init__.py
│       ├── cli.py              # CLI entry point
│       ├── parser.py           # Main parser logic
│       ├── patterns.py         # Pattern detection
│       ├── extractors.py       # Stream extraction by pattern
│       ├── models.py           # Data classes
│       ├── validators.py       # Validation logic
│       ├── constants.py        # Regex patterns, column indices
│       ├── utils.py            # Helper functions
│       ├── exceptions.py       # Custom exception classes
│       ├── normalization.py    # Instructor name normalization
│       └── exporters.py        # JSON/CSV/Excel export functions
├── tests/
│   ├── __init__.py
│   ├── test_parser.py
│   ├── test_patterns.py
│   ├── test_extractors.py
│   └── fixtures/
│       └── sample_form1.xlsx
└── output/                     # Default output directory
```

---

## 14. Constants Reference

```python
# constants.py

# Column indices (0-based)
COL_NUMBER = 0
COL_SUBJECT = 1
COL_SPECIALTY = 3
COL_GROUP = 4
COL_CREDITS = 5
COL_LANGUAGE = 6
COL_STUDENTS = 7
COL_LECTURES = 8
COL_PRACTICALS = 9
COL_LABS = 10

# Regex patterns
EXPLICIT_SUBGROUP_PATTERN = r'/[12]/|\\[12]\\|\s-[12]$'
STUDY_FORM_PATTERN = r'/[уг]/'
GROUP_NAME_PATTERN = r'^[А-ЯӘҒҚҢӨҰҮІа-яәғқңөұүі]+-\d{2}'

# Instructor detection markers
INSTRUCTOR_MARKERS = ['проф', 'а.о.', 'с.п.', 'асс', 'доц', 'д.', 'prof.', 'prof']

# Data start markers
DATA_START_MARKERS = ['1', '2 семестр', '2семестр']

# Languages
LANGUAGE_KAZAKH = 'каз'
LANGUAGE_RUSSIAN = 'орыс'
VALID_LANGUAGES = {LANGUAGE_KAZAKH, LANGUAGE_RUSSIAN}

# Sheet names
SHEET_NAMES = ['оод (2)', 'эиб', 'юр', 'стр', 'эл', 'ттт', 'нд']

# Known instructor column positions per sheet
KNOWN_INSTRUCTOR_COLUMNS = {
    'оод (2)': 25,
    'эиб': 25,
    'юр': 25,
    'стр': 26,
    'эл': 25,
    'ттт': 25,
    'нд': 26,
}

# Academic weeks
ODD_WEEKS_COUNT = 8   # 1, 3, 5, 7, 9, 11, 13, 15
EVEN_WEEKS_COUNT = 7  # 2, 4, 6, 8, 10, 12, 14
TOTAL_WEEKS = ODD_WEEKS_COUNT + EVEN_WEEKS_COUNT  # 15

# Pattern names
PATTERN_1A = '1a'
PATTERN_1B = '1b'
PATTERN_IMPLICIT_SUBGROUP = 'implicit_subgroup'
PATTERN_EXPLICIT_SUBGROUP = 'explicit_subgroup'
```

---

## 15. Example Usage

```python
from form1_parser import Form1Parser

# Parse file
parser = Form1Parser()
result = parser.parse("form-1.xlsx")

# Access results
print(f"Total streams: {result.total_streams}")
print(f"Total subjects: {result.total_subjects}")

# Iterate streams
for stream in result.streams:
    print(f"{stream.subject} | {stream.stream_type.value} | {stream.instructor}")

# Export to JSON
result.to_json("output.json")

# Export to CSV
result.to_csv("output_dir/")

# Get subject summary
for subject in result.subjects:
    print(f"{subject.subject}: {subject.total_streams} streams")
    print(f"  Pattern: {subject.pattern}")
    print(f"  Instructors: {', '.join(subject.instructors)}")
```

---

## 16. Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Jan 2025 | Initial specification |
| 1.1 | Jan 2026 | Corrected patterns (removed "Pattern 2"), added missing constants, updated file structure, added model serialization methods |

---

*End of Specification*