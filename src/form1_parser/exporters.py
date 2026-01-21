"""Export functionality for Form-1 parser results."""

import csv
import json
from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd

from .models import ParseResult


class BaseExporter(ABC):
    """Base class for exporters."""

    @abstractmethod
    def export(self, result: ParseResult, output_path: str | Path) -> None:
        """Export parse result to file.

        Args:
            result: ParseResult to export
            output_path: Path to output file or directory
        """
        pass


class JSONExporter(BaseExporter):
    """Export to JSON format."""

    def __init__(self, indent: int = 2, ensure_ascii: bool = False):
        """Initialize exporter.

        Args:
            indent: JSON indentation level
            ensure_ascii: If False, allows non-ASCII characters
        """
        self.indent = indent
        self.ensure_ascii = ensure_ascii

    def export(self, result: ParseResult, output_path: str | Path) -> None:
        """Export parse result to JSON file.

        Args:
            result: ParseResult to export
            output_path: Path to output JSON file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(
                result.to_dict(),
                f,
                indent=self.indent,
                ensure_ascii=self.ensure_ascii,
            )


class CSVExporter(BaseExporter):
    """Export to CSV format (multiple files)."""

    def export(self, result: ParseResult, output_path: str | Path) -> None:
        """Export parse result to CSV files.

        Creates three files:
        - streams.csv: All streams
        - subjects.csv: Subject summaries
        - summary.csv: Overall summary

        Args:
            result: ParseResult to export
            output_path: Path to output directory
        """
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)

        self._export_streams(result, output_dir / "streams.csv")
        self._export_subjects(result, output_dir / "subjects.csv")
        self._export_summary(result, output_dir / "summary.csv")

    def _export_streams(self, result: ParseResult, output_path: Path) -> None:
        """Export streams to CSV."""
        rows = []
        for stream in result.streams:
            rows.append(
                {
                    "id": stream.id,
                    "subject": stream.subject,
                    "stream_type": stream.stream_type.value,
                    "instructor": stream.instructor,
                    "language": stream.language,
                    "total_hours": stream.hours.total,
                    "odd_week_hours": stream.hours.odd_week,
                    "even_week_hours": stream.hours.even_week,
                    "groups": "; ".join(stream.groups),
                    "student_count": stream.student_count,
                    "sheet": stream.sheet,
                    "rows": "; ".join(map(str, stream.rows)),
                    "is_subgroup": stream.is_subgroup,
                    "is_implicit_subgroup": stream.is_implicit_subgroup,
                }
            )

        self._write_csv(output_path, rows)

    def _export_subjects(self, result: ParseResult, output_path: Path) -> None:
        """Export subjects to CSV."""
        rows = []
        for subject in result.subjects:
            rows.append(
                {
                    "subject": subject.subject,
                    "sheet": subject.sheet,
                    "pattern": subject.pattern,
                    "lecture_streams": len(subject.lecture_streams),
                    "practical_streams": len(subject.practical_streams),
                    "lab_streams": len(subject.lab_streams),
                    "total_streams": subject.total_streams,
                    "total_hours": subject.total_hours,
                    "instructors": "; ".join(subject.instructors),
                }
            )

        self._write_csv(output_path, rows)

    def _export_summary(self, result: ParseResult, output_path: Path) -> None:
        """Export summary to CSV."""
        rows = [
            {
                "metric": "file_path",
                "value": result.file_path,
            },
            {
                "metric": "parse_date",
                "value": result.parse_date,
            },
            {
                "metric": "sheets_processed",
                "value": len(result.sheets_processed),
            },
            {
                "metric": "total_subjects",
                "value": result.total_subjects,
            },
            {
                "metric": "total_streams",
                "value": result.total_streams,
            },
            {
                "metric": "errors",
                "value": len(result.errors),
            },
            {
                "metric": "warnings",
                "value": len(result.warnings),
            },
        ]

        self._write_csv(output_path, rows)

    def _write_csv(self, output_path: Path, rows: list[dict]) -> None:
        """Write rows to CSV file."""
        if not rows:
            return

        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)


class ExcelExporter(BaseExporter):
    """Export to Excel format (single workbook with multiple sheets)."""

    def export(self, result: ParseResult, output_path: str | Path) -> None:
        """Export parse result to Excel file.

        Creates workbook with sheets:
        - Streams: All streams
        - Subjects: Subject summaries
        - Summary: Overall summary
        - Errors: Error list
        - Warnings: Warning list

        Args:
            result: ParseResult to export
            output_path: Path to output Excel file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            self._export_streams_sheet(result, writer)
            self._export_subjects_sheet(result, writer)
            self._export_summary_sheet(result, writer)
            self._export_errors_sheet(result, writer)
            self._export_warnings_sheet(result, writer)

    def _export_streams_sheet(
        self, result: ParseResult, writer: pd.ExcelWriter
    ) -> None:
        """Export streams to Excel sheet."""
        rows = []
        for stream in result.streams:
            rows.append(
                {
                    "ID": stream.id,
                    "Subject": stream.subject,
                    "Type": stream.stream_type.value,
                    "Instructor": stream.instructor,
                    "Language": stream.language,
                    "Total Hours": stream.hours.total,
                    "Odd Week": stream.hours.odd_week,
                    "Even Week": stream.hours.even_week,
                    "Groups": "; ".join(stream.groups),
                    "Students": stream.student_count,
                    "Sheet": stream.sheet,
                    "Rows": "; ".join(map(str, stream.rows)),
                    "Is Subgroup": stream.is_subgroup,
                    "Is Implicit Subgroup": stream.is_implicit_subgroup,
                }
            )

        df = pd.DataFrame(rows)
        df.to_excel(writer, sheet_name="Streams", index=False)

    def _export_subjects_sheet(
        self, result: ParseResult, writer: pd.ExcelWriter
    ) -> None:
        """Export subjects to Excel sheet."""
        rows = []
        for subject in result.subjects:
            rows.append(
                {
                    "Subject": subject.subject,
                    "Sheet": subject.sheet,
                    "Pattern": subject.pattern,
                    "Lecture Streams": len(subject.lecture_streams),
                    "Practical Streams": len(subject.practical_streams),
                    "Lab Streams": len(subject.lab_streams),
                    "Total Streams": subject.total_streams,
                    "Total Hours": subject.total_hours,
                    "Instructors": "; ".join(subject.instructors),
                }
            )

        df = pd.DataFrame(rows)
        df.to_excel(writer, sheet_name="Subjects", index=False)

    def _export_summary_sheet(
        self, result: ParseResult, writer: pd.ExcelWriter
    ) -> None:
        """Export summary to Excel sheet."""
        rows = [
            {"Metric": "File Path", "Value": result.file_path},
            {"Metric": "Parse Date", "Value": result.parse_date},
            {
                "Metric": "Sheets Processed",
                "Value": ", ".join(result.sheets_processed),
            },
            {"Metric": "Total Subjects", "Value": result.total_subjects},
            {"Metric": "Total Streams", "Value": result.total_streams},
            {"Metric": "Errors", "Value": len(result.errors)},
            {"Metric": "Warnings", "Value": len(result.warnings)},
        ]

        df = pd.DataFrame(rows)
        df.to_excel(writer, sheet_name="Summary", index=False)

    def _export_errors_sheet(
        self, result: ParseResult, writer: pd.ExcelWriter
    ) -> None:
        """Export errors to Excel sheet."""
        rows = [{"Error": error} for error in result.errors]
        df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["Error"])
        df.to_excel(writer, sheet_name="Errors", index=False)

    def _export_warnings_sheet(
        self, result: ParseResult, writer: pd.ExcelWriter
    ) -> None:
        """Export warnings to Excel sheet."""
        rows = [{"Warning": warning} for warning in result.warnings]
        df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["Warning"])
        df.to_excel(writer, sheet_name="Warnings", index=False)


def get_exporter(format_type: str) -> BaseExporter:
    """Get appropriate exporter for format type.

    Args:
        format_type: Export format ('json', 'csv', 'excel')

    Returns:
        Exporter instance

    Raises:
        ValueError: If format type is not supported
    """
    exporters = {
        "json": JSONExporter,
        "csv": CSVExporter,
        "excel": ExcelExporter,
    }

    if format_type not in exporters:
        raise ValueError(
            f"Unsupported format: {format_type}. Supported: {', '.join(exporters.keys())}"
        )

    return exporters[format_type]()
