"""Export functions for schedule results."""

import json
from pathlib import Path

from .models import ScheduleResult


def export_schedule_json(result: ScheduleResult, output_path: Path | str) -> None:
    """Export schedule result to JSON file.

    Args:
        result: ScheduleResult to export
        output_path: Path to output JSON file
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with open(output, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)


def load_parsed_data(input_path: Path | str) -> dict:
    """Load parsed Form-1 data from JSON file.

    Args:
        input_path: Path to parsed JSON file

    Returns:
        Dictionary with parsed data
    """
    with open(input_path, encoding="utf-8") as f:
        return json.load(f)
