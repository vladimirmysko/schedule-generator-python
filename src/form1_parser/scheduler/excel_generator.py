"""Excel schedule generator from JSON data."""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, Side

# Localization strings
STRINGS_KAZ = {
    "university": "Батыс Қазақстан инновациялық-технологиялық университеті",
    "schedule_title": "САБАҚ КЕСТЕСІ",
    "approval": "Бекітемін",
    "position": "ОЖ бойынша проректор м.а. ______________",
    "date_line": '"___" _____________ 2025 ж.',
    "agreement": "Келісілді СТИ директоры ______________",
    "day_header": "Күн",
    "time_header": "Уақыт",
    "course_template": "{} курс",
    "days": {
        "monday": "Дүйсенбі",
        "tuesday": "Сейсенбі",
        "wednesday": "Сәрсенбі",
        "thursday": "Бейсенбі",
        "friday": "Жұма",
        "saturday": "Сенбі",
    },
}

STRINGS_RUS = {
    "university": "Западно-Казахстанский инновационно-технологический университет",
    "schedule_title": "РАСПИСАНИЕ ЗАНЯТИЙ",
    "approval": "Утверждаю",
    "position": "и.о. проректора по УР ______________",
    "date_line": '"___" _____________ 2025 г.',
    "agreement": "Согласовано директор СТИ ______________",
    "day_header": "День",
    "time_header": "Время",
    "course_template": "{} курс",
    "days": {
        "monday": "Понедельник",
        "tuesday": "Вторник",
        "wednesday": "Среда",
        "thursday": "Четверг",
        "friday": "Пятница",
        "saturday": "Суббота",
    },
}

# Column widths
COLUMN_WIDTHS = {"A": 12.0, "B": 14.0, "C": 5.0, "D": 20.0, "E": 20.0, "F": 20.0}

# Day row ranges (start_row, end_row)
DAY_ROW_RANGES = {
    "monday": (10, 16),
    "tuesday": (17, 23),
    "wednesday": (24, 30),
    "thursday": (31, 37),
    "friday": (38, 44),
}

# Days in order
DAYS_ORDER = ["monday", "tuesday", "wednesday", "thursday", "friday"]

# Fonts
FONT_TITLE = Font(name="Times New Roman", size=16, bold=True)
FONT_HEADER = Font(name="Times New Roman", size=12, bold=True)
FONT_GROUP = Font(name="Times New Roman", size=14, bold=True)
FONT_DAY = Font(name="Times New Roman", size=11, bold=True)
FONT_TIME = Font(name="Times New Roman", size=10, bold=False)
FONT_CELL = Font(name="Times New Roman", size=11, bold=False)
FONT_APPROVAL = Font(name="Times New Roman", size=11, bold=False)

# Alignments
ALIGN_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
ALIGN_CENTER_NOWRAP = Alignment(horizontal="center", vertical="center", wrap_text=False)
ALIGN_RIGHT = Alignment(horizontal="right", vertical="center", wrap_text=False)

# Borders
THIN_BORDER = Border(
    left=Side(style="thin"),
    right=Side(style="thin"),
    top=Side(style="thin"),
    bottom=Side(style="thin"),
)

# Merged cells for the layout
MERGED_CELLS = [
    "A2:F2",  # University name
    "A6:F6",  # Schedule title
    "A8:F8",  # Course/year
    "A10:A16",  # Monday label
    "A17:A23",  # Tuesday label
    "A24:A30",  # Wednesday label
    "A31:A37",  # Thursday label
    "A38:A44",  # Friday label
    "A46:C46",  # Agreement text
    "A47:C47",  # Date line
]

# Default time slots for first shift (slots 1-7)
DEFAULT_TIME_SLOTS = {
    1: "09:00-09:50",
    2: "10:00-10:50",
    3: "11:00-11:50",
    4: "12:00-12:50",
    5: "13:00-13:50",
    6: "14:00-14:50",
    7: "15:00-15:50",
}


@dataclass
class GeneratorConfig:
    """Configuration for schedule generation."""

    language: Literal["kaz", "rus"]
    year: int
    week_type: Literal["odd", "even"]
    first_slot: int = 1
    slots_per_day: int = 7


class ScheduleExcelGenerator:
    """Generates Excel schedule files from JSON data."""

    def __init__(self, config: GeneratorConfig):
        """Initialize generator with configuration.

        Args:
            config: Generator configuration with language, year, and week type.
        """
        self.config = config
        self.strings = STRINGS_KAZ if config.language == "kaz" else STRINGS_RUS

    def load_json(self, path: Path) -> dict:
        """Load schedule data from JSON file.

        Args:
            path: Path to JSON file.

        Returns:
            Parsed JSON data as dictionary.
        """
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def get_year_from_group(group: str) -> int:
        """Extract year from group code.

        Args:
            group: Group code like 'АРХ-21 О'.

        Returns:
            Year number (1-4) or 0 if not found.
        """
        match = re.search(r"-(\d)", group)
        return int(match.group(1)) if match else 0

    @staticmethod
    def is_russian_group(group: str) -> bool:
        """Check if group is Russian language.

        Language is determined by the second digit of the group code:
        - Odd second digit (1, 3, 5, 7, 9) → Kazakh
        - Even second digit (2, 4, 6, 8, 0) → Russian

        Examples:
            АУ-31 О → 1 (odd) → Kazakh
            ЮР-33 О /у/ → 3 (odd) → Kazakh
            СТР-22 О → 2 (even) → Russian
            АРХ-22 О → 2 (even) → Russian

        Args:
            group: Group code.

        Returns:
            True if group is Russian (even second digit).
        """
        match = re.search(r"-(\d)(\d)", group)
        if match:
            second_digit = int(match.group(2))
            return second_digit % 2 == 0
        return False

    def filter_assignments(self, data: dict) -> tuple[list[dict], list[str]]:
        """Filter assignments by configuration criteria.

        Args:
            data: Full schedule data with assignments.

        Returns:
            Tuple of (filtered assignments, sorted group list).
        """
        assignments = data.get("assignments", [])

        # Filter by week type
        filtered = [
            a for a in assignments if a["week_type"] in (self.config.week_type, "both")
        ]

        # Collect groups matching target year
        year_groups: set[str] = set()
        for a in filtered:
            for g in a["groups"]:
                if self.get_year_from_group(g) == self.config.year:
                    year_groups.add(g)

        # Filter by language
        if self.config.language == "rus":
            year_groups = {g for g in year_groups if self.is_russian_group(g)}
        else:
            year_groups = {g for g in year_groups if not self.is_russian_group(g)}

        return filtered, sorted(year_groups)

    def group_into_sheets(
        self, groups: list[str], max_per_sheet: int = 3
    ) -> list[list[str]]:
        """Split groups into sheets with maximum groups per sheet.

        Args:
            groups: List of group names.
            max_per_sheet: Maximum groups per sheet (default 3).

        Returns:
            List of group lists, one per sheet.
        """
        sheets = []
        for i in range(0, len(groups), max_per_sheet):
            sheets.append(groups[i : i + max_per_sheet])
        return sheets

    @staticmethod
    def sanitize_sheet_name(name: str) -> str:
        """Sanitize sheet name by removing invalid characters.

        Excel sheet names cannot contain: / \\ * ? : [ ]

        Args:
            name: Original sheet name.

        Returns:
            Sanitized sheet name (max 31 chars).
        """
        # Replace invalid characters
        invalid_chars = r"/\*?:[]"
        for char in invalid_chars:
            name = name.replace(char, "")
        return name[:31]

    def build_schedule_grid(
        self, assignments: list[dict], groups: list[str]
    ) -> dict[str, dict[int, dict[str, dict | None]]]:
        """Build 2D schedule grid for given groups.

        Args:
            assignments: List of assignment dictionaries.
            groups: List of group names for this sheet.

        Returns:
            Grid structure: {day: {slot: {group: assignment or None}}}
        """
        grid: dict[str, dict[int, dict[str, dict | None]]] = {}

        for day in DAYS_ORDER:
            grid[day] = {}
            for slot in range(
                self.config.first_slot,
                self.config.first_slot + self.config.slots_per_day,
            ):
                grid[day][slot] = {group: None for group in groups}

        for assignment in assignments:
            day = assignment["day"]
            slot = assignment["slot"]
            if day not in grid:
                continue
            if slot not in grid[day]:
                continue
            for group in assignment["groups"]:
                if group in groups:
                    grid[day][slot][group] = assignment

        return grid

    def format_cell_content(self, assignment: dict) -> str:
        """Format assignment for cell display.

        Args:
            assignment: Assignment dictionary.

        Returns:
            Formatted multi-line string for cell.
        """
        subject = assignment["subject"].upper()
        instructor = assignment["instructor"]
        # Clean instructor name
        instructor = instructor.replace("а.о.", "").replace("қ.проф.", "").strip()
        room_info = f"{assignment['room']}, {assignment['room_address']}"
        return f"{subject}\n{instructor}\n{room_info}"

    def create_workbook(self, assignments: list[dict], groups: list[str]) -> Workbook:
        """Create Excel workbook with schedule.

        Args:
            assignments: Filtered assignments.
            groups: Groups to include.

        Returns:
            Populated Workbook object.
        """
        wb = Workbook()
        wb.remove(wb.active)

        if not groups:
            # Create empty sheet if no groups
            ws = wb.create_sheet(title="Empty")
            return wb

        # Split groups into sheets (max 3 per sheet)
        sheets = self.group_into_sheets(groups)

        for sheet_groups in sheets:
            # Sheet name: comma-separated group names, sanitized for Excel
            sheet_name = self.sanitize_sheet_name(", ".join(sheet_groups))
            ws = wb.create_sheet(title=sheet_name)
            self.setup_sheet(ws, sheet_groups)

            # Build and fill schedule
            grid = self.build_schedule_grid(assignments, sheet_groups)
            self.fill_schedule(ws, grid, sheet_groups)

        return wb

    def setup_sheet(self, ws, groups: list[str]) -> None:
        """Set up sheet structure with headers and formatting.

        Args:
            ws: Worksheet to set up.
            groups: Group names for this sheet.
        """
        # Set column widths
        for col, width in COLUMN_WIDTHS.items():
            ws.column_dimensions[col].width = width

        # Set row heights
        ws.row_dimensions[9].height = 30.0
        for row in range(10, 45):
            ws.row_dimensions[row].height = 55.0

        # Merge cells
        for merge_range in MERGED_CELLS:
            ws.merge_cells(merge_range)

        # Setup headers
        self.setup_headers(ws, groups)

        # Setup schedule grid structure
        self.setup_grid(ws)

    def setup_headers(self, ws, groups: list[str]) -> None:
        """Set up header rows (1-9).

        Args:
            ws: Worksheet.
            groups: Group names for column headers.
        """
        # Row 2: University name
        ws["A2"] = self.strings["university"]
        ws["A2"].font = FONT_TITLE
        ws["A2"].alignment = ALIGN_CENTER

        # Row 3-5: Approval text (right-aligned in F column)
        ws["F3"] = self.strings["approval"]
        ws["F3"].font = FONT_APPROVAL
        ws["F3"].alignment = ALIGN_RIGHT

        ws["F4"] = self.strings["position"]
        ws["F4"].font = FONT_APPROVAL
        ws["F4"].alignment = ALIGN_RIGHT

        ws["F5"] = self.strings["date_line"]
        ws["F5"].font = FONT_APPROVAL
        ws["F5"].alignment = ALIGN_RIGHT

        # Row 6: Schedule title
        ws["A6"] = self.strings["schedule_title"]
        ws["A6"].font = FONT_TITLE
        ws["A6"].alignment = ALIGN_CENTER

        # Row 7: Date range (placeholder)
        # This would be generated based on academic calendar
        ws["A7"] = ""

        # Row 8: Course/year
        course_text = self.strings["course_template"].format(self.config.year)
        ws["A8"] = course_text
        ws["A8"].font = FONT_TITLE
        ws["A8"].alignment = ALIGN_CENTER

        # Row 9: Column headers
        ws["A9"] = self.strings["day_header"]
        ws["A9"].font = FONT_HEADER
        ws["A9"].alignment = ALIGN_CENTER
        ws["A9"].border = THIN_BORDER

        ws["B9"] = self.strings["time_header"]
        ws["B9"].font = FONT_HEADER
        ws["B9"].alignment = ALIGN_CENTER
        ws["B9"].border = THIN_BORDER

        ws["C9"] = "№"
        ws["C9"].font = FONT_HEADER
        ws["C9"].alignment = ALIGN_CENTER
        ws["C9"].border = THIN_BORDER

        # Group columns (D, E, F)
        group_cols = ["D", "E", "F"]
        for i, col in enumerate(group_cols):
            if i < len(groups):
                ws[f"{col}9"] = groups[i]
                ws[f"{col}9"].font = FONT_GROUP
            else:
                ws[f"{col}9"] = ""
            ws[f"{col}9"].alignment = ALIGN_CENTER
            ws[f"{col}9"].border = THIN_BORDER

        # Row 46-47: Agreement text
        ws["A46"] = self.strings["agreement"]
        ws["A46"].font = FONT_APPROVAL
        ws["A46"].alignment = Alignment(horizontal="left", vertical="center")

        ws["A47"] = self.strings["date_line"]
        ws["A47"].font = FONT_APPROVAL
        ws["A47"].alignment = Alignment(horizontal="left", vertical="center")

    def setup_grid(self, ws) -> None:
        """Set up the schedule grid (rows 10-44).

        Args:
            ws: Worksheet.
        """
        for day in DAYS_ORDER:
            start_row, end_row = DAY_ROW_RANGES[day]

            # Day name in first cell of merged range
            ws[f"A{start_row}"] = self.strings["days"][day]
            ws[f"A{start_row}"].font = FONT_DAY
            ws[f"A{start_row}"].alignment = ALIGN_CENTER

            # Set borders for day column (merged cell)
            for row in range(start_row, end_row + 1):
                ws[f"A{row}"].border = THIN_BORDER

            # Time slots and slot numbers
            for i, row in enumerate(range(start_row, end_row + 1)):
                slot_num = self.config.first_slot + i
                time_range = DEFAULT_TIME_SLOTS.get(slot_num, "")

                # Time column (B)
                ws[f"B{row}"] = time_range
                ws[f"B{row}"].font = FONT_TIME
                ws[f"B{row}"].alignment = ALIGN_CENTER
                ws[f"B{row}"].border = THIN_BORDER

                # Slot number column (C)
                ws[f"C{row}"] = slot_num
                ws[f"C{row}"].font = FONT_TIME
                ws[f"C{row}"].alignment = ALIGN_CENTER
                ws[f"C{row}"].border = THIN_BORDER

                # Group columns (D, E, F) - empty cells with borders
                for col in ["D", "E", "F"]:
                    ws[f"{col}{row}"].border = THIN_BORDER
                    ws[f"{col}{row}"].alignment = ALIGN_CENTER
                    ws[f"{col}{row}"].font = FONT_CELL

    def fill_schedule(
        self,
        ws,
        grid: dict[str, dict[int, dict[str, dict | None]]],
        groups: list[str],
    ) -> None:
        """Fill schedule cells with assignment data.

        Args:
            ws: Worksheet.
            grid: Schedule grid from build_schedule_grid.
            groups: Group names in order.
        """
        group_cols = ["D", "E", "F"]

        for day in DAYS_ORDER:
            start_row, _ = DAY_ROW_RANGES[day]

            if day not in grid:
                continue

            for i, slot in enumerate(sorted(grid[day].keys())):
                row = start_row + i

                for j, group in enumerate(groups):
                    if j >= len(group_cols):
                        break

                    col = group_cols[j]
                    assignment = grid[day][slot].get(group)

                    if assignment:
                        ws[f"{col}{row}"] = self.format_cell_content(assignment)

    def save(self, wb: Workbook, output_path: Path) -> None:
        """Save workbook to file.

        Args:
            wb: Workbook to save.
            output_path: Output file path.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(output_path)


def generate_schedule_excel(
    input_path: Path,
    output_dir: Path,
    language: str | None = None,
    year: int | None = None,
    week_type: str | None = None,
) -> list[Path]:
    """Generate Excel schedule files from JSON.

    Args:
        input_path: Path to schedule JSON file.
        output_dir: Output directory for Excel files.
        language: Filter by language ('kaz' or 'rus'), or None for all.
        year: Filter by year (1-4), or None for all.
        week_type: Filter by week type ('odd' or 'even'), or None for all.

    Returns:
        List of generated file paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_files: list[Path] = []

    # Determine what to generate
    languages = [language] if language else ["kaz", "rus"]
    years = [year] if year else [1, 2, 3, 4]
    week_types = [week_type] if week_type else ["odd", "even"]

    for lang in languages:
        for yr in years:
            for wt in week_types:
                config = GeneratorConfig(
                    language=lang,  # type: ignore
                    year=yr,
                    week_type=wt,  # type: ignore
                )
                generator = ScheduleExcelGenerator(config)

                # Load and filter data
                data = generator.load_json(input_path)
                assignments, groups = generator.filter_assignments(data)

                if not groups:
                    # Skip if no groups match criteria
                    continue

                # Create and save workbook
                wb = generator.create_workbook(assignments, groups)
                output_file = output_dir / f"schedule_{lang}_{yr}y_{wt}.xlsx"
                generator.save(wb, output_file)
                generated_files.append(output_file)

    return generated_files
