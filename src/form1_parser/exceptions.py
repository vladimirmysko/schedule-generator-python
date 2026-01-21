"""Custom exceptions for Form-1 parser."""


class ParseError(Exception):
    """Base exception for parser errors."""

    pass


class SheetNotFoundError(ParseError):
    """Sheet not found in workbook."""

    def __init__(self, sheet_name: str, available_sheets: list[str] | None = None):
        self.sheet_name = sheet_name
        self.available_sheets = available_sheets or []
        message = f"Sheet '{sheet_name}' not found in workbook"
        if self.available_sheets:
            message += f". Available sheets: {', '.join(self.available_sheets)}"
        super().__init__(message)


class DataStartNotFoundError(ParseError):
    """Could not locate data start row."""

    def __init__(self, sheet_name: str):
        self.sheet_name = sheet_name
        super().__init__(
            f"Could not locate data start row in sheet '{sheet_name}'. "
            "Expected marker '1', '2 семестр', or '2семестр' in column 0."
        )


class InstructorColumnNotFoundError(ParseError):
    """Could not locate instructor column."""

    def __init__(self, sheet_name: str):
        self.sheet_name = sheet_name
        super().__init__(
            f"Could not locate instructor column in sheet '{sheet_name}'. "
            "Expected column with instructor markers (проф, а.о., с.п., асс, доц)."
        )


class InvalidDataError(ParseError):
    """Data validation failed."""

    def __init__(self, message: str, sheet_name: str | None = None, row: int | None = None):
        self.sheet_name = sheet_name
        self.row = row
        location = ""
        if sheet_name:
            location += f" in sheet '{sheet_name}'"
        if row is not None:
            location += f" at row {row}"
        super().__init__(f"Invalid data{location}: {message}")


class InvalidHoursError(ParseError):
    """Hours value doesn't fit the formula."""

    def __init__(self, total_hours: int):
        self.total_hours = total_hours
        super().__init__(
            f"Invalid total hours: {total_hours}. "
            "Must satisfy: 8×odd + 7×even = total (remainder must be 0, 7, or 8 when divided by 15)"
        )
