"""Main Form-1 parser class."""

from datetime import datetime
from pathlib import Path

import pandas as pd

from .constants import (
    COL_GROUP,
    COL_LABS,
    COL_LANGUAGE,
    COL_LECTURES,
    COL_PRACTICALS,
    COL_STUDENTS,
    COL_SUBJECT,
    SHEET_NAMES,
)
from .exceptions import (
    DataStartNotFoundError,
    InstructorColumnNotFoundError,
    InvalidHoursError,
    ParseError,
    SheetNotFoundError,
)
from .extractors import get_extractor
from .models import ParseResult, Stream, SubjectSummary, StreamType
from .patterns import detect_pattern
from .utils import (
    find_data_start_row,
    find_instructor_column,
    forward_fill_subject_names,
    safe_int,
    safe_str,
)


class Form1Parser:
    """Parser for Form-1 Excel workload spreadsheets."""

    def __init__(self, sheet_names: list[str] | None = None):
        """Initialize parser.

        Args:
            sheet_names: List of sheet names to process. Defaults to standard 7 sheets.
        """
        self.sheet_names = sheet_names or SHEET_NAMES

    def parse(self, file_path: str | Path) -> ParseResult:
        """Parse a Form-1 Excel file.

        Args:
            file_path: Path to the Excel file

        Returns:
            ParseResult with all extracted data
        """
        file_path = Path(file_path)

        result = ParseResult(
            file_path=str(file_path),
            parse_date=datetime.now().isoformat(),
        )

        if not file_path.exists():
            result.errors.append(f"File not found: {file_path}")
            return result

        try:
            excel_file = pd.ExcelFile(file_path)
        except Exception as e:
            result.errors.append(f"Failed to open Excel file: {e}")
            return result

        available_sheets = excel_file.sheet_names

        for sheet_name in self.sheet_names:
            if sheet_name not in available_sheets:
                result.warnings.append(
                    f"Sheet '{sheet_name}' not found. Available: {', '.join(available_sheets)}"
                )
                continue

            try:
                sheet_result = self._process_sheet(excel_file, sheet_name)
                result.subjects.extend(sheet_result["subjects"])
                result.streams.extend(sheet_result["streams"])
                result.warnings.extend(sheet_result["warnings"])
                result.sheets_processed.append(sheet_name)
            except ParseError as e:
                result.errors.append(f"Sheet '{sheet_name}': {e}")
            except Exception as e:
                result.errors.append(f"Sheet '{sheet_name}': Unexpected error - {e}")

        return result

    def _process_sheet(self, excel_file: pd.ExcelFile, sheet_name: str) -> dict:
        """Process a single sheet.

        Args:
            excel_file: Open Excel file
            sheet_name: Name of sheet to process

        Returns:
            Dictionary with subjects, streams, and warnings
        """
        subjects: list[SubjectSummary] = []
        streams: list[Stream] = []
        warnings: list[str] = []

        # Read sheet with no header (we'll handle structure ourselves)
        df = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)

        # Find data start row
        try:
            data_start = find_data_start_row(df, sheet_name)
        except DataStartNotFoundError as e:
            raise e

        # Find instructor column
        try:
            instructor_col = find_instructor_column(df, sheet_name)
        except InstructorColumnNotFoundError as e:
            raise e

        # Forward fill subject names
        df = forward_fill_subject_names(df)

        # Extract data from start row onwards
        data_df = df.iloc[data_start:].copy()

        # Create working DataFrame with named columns
        working_df = self._create_working_dataframe(data_df, instructor_col)

        # Group by subject
        subject_groups = working_df.groupby("subject", sort=False)

        for subject_name, subject_data in subject_groups:
            if pd.isna(subject_name) or not str(subject_name).strip():
                continue

            try:
                subject_summary = self._process_subject(
                    str(subject_name), subject_data, sheet_name
                )
                subjects.append(subject_summary)
                streams.extend(subject_summary.lecture_streams)
                streams.extend(subject_summary.practical_streams)
                streams.extend(subject_summary.lab_streams)
            except InvalidHoursError as e:
                warnings.append(f"Subject '{subject_name}': {e}")
            except Exception as e:
                warnings.append(f"Subject '{subject_name}': Failed to process - {e}")

        return {
            "subjects": subjects,
            "streams": streams,
            "warnings": warnings,
        }

    def _create_working_dataframe(
        self, data_df: pd.DataFrame, instructor_col: int
    ) -> pd.DataFrame:
        """Create a working DataFrame with named columns.

        Args:
            data_df: Raw data DataFrame
            instructor_col: Index of instructor column

        Returns:
            DataFrame with named columns
        """
        working_data = []

        for idx, row in data_df.iterrows():
            working_data.append(
                {
                    "subject": safe_str(row.iloc[COL_SUBJECT]),
                    "group": safe_str(row.iloc[COL_GROUP]),
                    "language": safe_str(row.iloc[COL_LANGUAGE]),
                    "students": safe_int(row.iloc[COL_STUDENTS]),
                    "lecture": safe_int(row.iloc[COL_LECTURES]),
                    "practical": safe_int(row.iloc[COL_PRACTICALS]),
                    "lab": safe_int(row.iloc[COL_LABS]),
                    "instructor": safe_str(row.iloc[instructor_col])
                    if instructor_col < len(row)
                    else "",
                    "original_index": idx,
                }
            )

        return pd.DataFrame(working_data)

    def _process_subject(
        self, subject_name: str, subject_data: pd.DataFrame, sheet_name: str
    ) -> SubjectSummary:
        """Process a single subject.

        Args:
            subject_name: Name of the subject
            subject_data: DataFrame containing rows for this subject
            sheet_name: Name of the source sheet

        Returns:
            SubjectSummary with extracted streams
        """
        # Detect pattern
        pattern = detect_pattern(subject_data, "group", "practical")

        # Get appropriate extractor
        extractor = get_extractor(pattern, subject_name, sheet_name)

        # Extract streams
        all_streams = extractor.extract(subject_data)

        # Separate by type
        lecture_streams = [s for s in all_streams if s.stream_type == StreamType.LECTURE]
        practical_streams = [s for s in all_streams if s.stream_type == StreamType.PRACTICAL]
        lab_streams = [s for s in all_streams if s.stream_type == StreamType.LAB]

        return SubjectSummary(
            subject=subject_name,
            sheet=sheet_name,
            pattern=pattern,
            lecture_streams=lecture_streams,
            practical_streams=practical_streams,
            lab_streams=lab_streams,
        )

    def validate(self, file_path: str | Path) -> dict:
        """Validate a Form-1 file structure without full parsing.

        Args:
            file_path: Path to the Excel file

        Returns:
            Dictionary with validation results
        """
        file_path = Path(file_path)
        validation = {
            "valid": True,
            "file_exists": False,
            "sheets_found": [],
            "sheets_missing": [],
            "errors": [],
            "warnings": [],
        }

        if not file_path.exists():
            validation["valid"] = False
            validation["errors"].append(f"File not found: {file_path}")
            return validation

        validation["file_exists"] = True

        try:
            excel_file = pd.ExcelFile(file_path)
        except Exception as e:
            validation["valid"] = False
            validation["errors"].append(f"Failed to open Excel file: {e}")
            return validation

        available_sheets = excel_file.sheet_names

        for sheet_name in self.sheet_names:
            if sheet_name in available_sheets:
                validation["sheets_found"].append(sheet_name)

                # Try to find data start and instructor column
                df = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)

                try:
                    find_data_start_row(df, sheet_name)
                except DataStartNotFoundError as e:
                    validation["warnings"].append(str(e))

                try:
                    find_instructor_column(df, sheet_name)
                except InstructorColumnNotFoundError as e:
                    validation["warnings"].append(str(e))
            else:
                validation["sheets_missing"].append(sheet_name)

        if validation["sheets_missing"]:
            validation["warnings"].append(
                f"Missing sheets: {', '.join(validation['sheets_missing'])}"
            )

        if not validation["sheets_found"]:
            validation["valid"] = False
            validation["errors"].append("No expected sheets found in workbook")

        return validation

    def get_stats(self, result: ParseResult) -> dict:
        """Get statistics from a parse result.

        Args:
            result: ParseResult from parsing

        Returns:
            Dictionary with statistics
        """
        stats = {
            "file_path": result.file_path,
            "parse_date": result.parse_date,
            "sheets_processed": len(result.sheets_processed),
            "total_subjects": result.total_subjects,
            "total_streams": result.total_streams,
            "streams_by_type": {
                "lecture": 0,
                "practical": 0,
                "lab": 0,
            },
            "streams_by_sheet": {},
            "patterns_used": {},
            "instructors_count": 0,
            "unique_instructors": set(),
            "errors_count": len(result.errors),
            "warnings_count": len(result.warnings),
        }

        for stream in result.streams:
            stats["streams_by_type"][stream.stream_type.value] += 1
            stats["unique_instructors"].add(stream.instructor)

            sheet = stream.sheet
            if sheet not in stats["streams_by_sheet"]:
                stats["streams_by_sheet"][sheet] = 0
            stats["streams_by_sheet"][sheet] += 1

        for subject in result.subjects:
            pattern = subject.pattern
            if pattern not in stats["patterns_used"]:
                stats["patterns_used"][pattern] = 0
            stats["patterns_used"][pattern] += 1

        stats["instructors_count"] = len(stats["unique_instructors"])
        stats["unique_instructors"] = sorted(stats["unique_instructors"])

        return stats
