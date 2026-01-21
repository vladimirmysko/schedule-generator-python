"""Form-1 Parser - Excel workload parser for university schedule generation.

This module provides tools to parse Form-1 (Ф-1) Excel workload spreadsheets
from West Kazakhstan Innovation and Technological University and extract
lecture, practical, and laboratory streams with their assigned instructors.

Example usage:
    from form1_parser import Form1Parser

    parser = Form1Parser()
    result = parser.parse("form-1.xlsx")

    print(f"Total streams: {result.total_streams}")
    print(f"Total subjects: {result.total_subjects}")

    for stream in result.streams:
        print(f"{stream.subject} | {stream.stream_type.value} | {stream.instructor}")

    # Export to JSON
    from form1_parser.exporters import JSONExporter
    exporter = JSONExporter()
    exporter.export(result, "output.json")
"""

from .exceptions import (
    DataStartNotFoundError,
    InstructorColumnNotFoundError,
    InvalidDataError,
    InvalidHoursError,
    ParseError,
    SheetNotFoundError,
)
from .exporters import CSVExporter, ExcelExporter, JSONExporter, get_exporter
from .models import ParseResult, Stream, StreamType, SubjectSummary, WeeklyHours
from .parser import Form1Parser
from .patterns import PatternDetector, detect_pattern

__version__ = "0.1.0"

__all__ = [
    # Main parser
    "Form1Parser",
    # Models
    "Stream",
    "StreamType",
    "WeeklyHours",
    "SubjectSummary",
    "ParseResult",
    # Exporters
    "JSONExporter",
    "CSVExporter",
    "ExcelExporter",
    "get_exporter",
    # Pattern detection
    "PatternDetector",
    "detect_pattern",
    # Exceptions
    "ParseError",
    "SheetNotFoundError",
    "DataStartNotFoundError",
    "InstructorColumnNotFoundError",
    "InvalidDataError",
    "InvalidHoursError",
]
