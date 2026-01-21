"""CLI entry point for Form-1 parser."""

from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from .exporters import get_exporter
from .parser import Form1Parser
from .scheduler import (
    create_scheduler,
    export_schedule_json,
    generate_schedule_excel,
    load_parsed_data,
)

app = typer.Typer(
    name="form1-parser",
    help="Parse Form-1 (Ф-1) Excel workload spreadsheets",
    add_completion=False,
)
console = Console()


class OutputFormat(str, Enum):
    """Output format options."""

    json = "json"
    csv = "csv"
    excel = "excel"


@app.command()
def parse(
    input_file: Annotated[
        Path,
        typer.Argument(help="Path to the Form-1 Excel file", exists=True, readable=True),
    ],
    output: Annotated[
        Optional[Path],
        typer.Option("-o", "--output", help="Output file or directory path"),
    ] = None,
    format: Annotated[
        OutputFormat,
        typer.Option("-f", "--format", help="Output format"),
    ] = OutputFormat.json,
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show detailed output"),
    ] = False,
) -> None:
    """Parse a Form-1 Excel file and extract streams."""
    parser = Form1Parser()

    with console.status("[bold green]Parsing file..."):
        result = parser.parse(input_file)

    # Show summary
    console.print(f"\n[bold]Parse Results for:[/bold] {input_file.name}")
    console.print(f"  Sheets processed: {len(result.sheets_processed)}")
    console.print(f"  Total subjects: {result.total_subjects}")
    console.print(f"  Total streams: {result.total_streams}")

    if result.errors:
        console.print(f"\n[bold red]Errors ({len(result.errors)}):[/bold red]")
        for error in result.errors:
            console.print(f"  [red]• {error}[/red]")

    if result.warnings and verbose:
        console.print(f"\n[bold yellow]Warnings ({len(result.warnings)}):[/bold yellow]")
        for warning in result.warnings:
            console.print(f"  [yellow]• {warning}[/yellow]")

    # Export if output path provided
    if output:
        exporter = get_exporter(format.value)

        if format == OutputFormat.csv:
            # CSV exports to directory
            output_path = output if output.is_dir() else output.parent / output.stem
        else:
            # JSON and Excel export to file
            if not output.suffix:
                output = output.with_suffix(f".{format.value}")
            output_path = output

        with console.status(f"[bold green]Exporting to {format.value}..."):
            exporter.export(result, output_path)

        console.print(f"\n[bold green]✓[/bold green] Exported to: {output_path}")
    elif verbose:
        # Show detailed results if no output file
        _show_detailed_results(result)


@app.command()
def validate(
    input_file: Annotated[
        Path,
        typer.Argument(help="Path to the Form-1 Excel file"),
    ],
) -> None:
    """Validate a Form-1 file structure without full parsing."""
    if not input_file.exists():
        console.print(f"[bold red]Error:[/bold red] File not found: {input_file}")
        raise typer.Exit(1)

    parser = Form1Parser()

    with console.status("[bold green]Validating file..."):
        validation = parser.validate(input_file)

    console.print(f"\n[bold]Validation Results for:[/bold] {input_file.name}")

    if validation["valid"]:
        console.print("[bold green]✓ File is valid[/bold green]")
    else:
        console.print("[bold red]✗ File has issues[/bold red]")

    console.print(f"\n  Sheets found: {len(validation['sheets_found'])}")
    if validation["sheets_found"]:
        console.print(f"    {', '.join(validation['sheets_found'])}")

    if validation["sheets_missing"]:
        console.print(f"\n  [yellow]Sheets missing: {len(validation['sheets_missing'])}[/yellow]")
        console.print(f"    {', '.join(validation['sheets_missing'])}")

    if validation["errors"]:
        console.print(f"\n[bold red]Errors ({len(validation['errors'])}):[/bold red]")
        for error in validation["errors"]:
            console.print(f"  [red]• {error}[/red]")

    if validation["warnings"]:
        console.print(f"\n[bold yellow]Warnings ({len(validation['warnings'])}):[/bold yellow]")
        for warning in validation["warnings"]:
            console.print(f"  [yellow]• {warning}[/yellow]")

    if not validation["valid"]:
        raise typer.Exit(1)


@app.command()
def stats(
    input_file: Annotated[
        Path,
        typer.Argument(help="Path to the Form-1 Excel file", exists=True, readable=True),
    ],
) -> None:
    """Show detailed statistics for a Form-1 file."""
    parser = Form1Parser()

    with console.status("[bold green]Analyzing file..."):
        result = parser.parse(input_file)
        statistics = parser.get_stats(result)

    console.print(f"\n[bold]Statistics for:[/bold] {input_file.name}")
    console.print(f"  Parse date: {statistics['parse_date']}")

    # Overview table
    overview_table = Table(title="Overview", show_header=False)
    overview_table.add_column("Metric", style="cyan")
    overview_table.add_column("Value", style="green")

    overview_table.add_row("Sheets Processed", str(statistics["sheets_processed"]))
    overview_table.add_row("Total Subjects", str(statistics["total_subjects"]))
    overview_table.add_row("Total Streams", str(statistics["total_streams"]))
    overview_table.add_row("Unique Instructors", str(statistics["instructors_count"]))
    overview_table.add_row("Errors", str(statistics["errors_count"]))
    overview_table.add_row("Warnings", str(statistics["warnings_count"]))

    console.print(overview_table)

    # Streams by type
    type_table = Table(title="Streams by Type")
    type_table.add_column("Type", style="cyan")
    type_table.add_column("Count", style="green")

    for stream_type, count in statistics["streams_by_type"].items():
        type_table.add_row(stream_type.capitalize(), str(count))

    console.print(type_table)

    # Streams by sheet
    if statistics["streams_by_sheet"]:
        sheet_table = Table(title="Streams by Sheet")
        sheet_table.add_column("Sheet", style="cyan")
        sheet_table.add_column("Count", style="green")

        for sheet, count in statistics["streams_by_sheet"].items():
            sheet_table.add_row(sheet, str(count))

        console.print(sheet_table)

    # Patterns used
    if statistics["patterns_used"]:
        pattern_table = Table(title="Patterns Detected")
        pattern_table.add_column("Pattern", style="cyan")
        pattern_table.add_column("Subjects", style="green")

        for pattern, count in statistics["patterns_used"].items():
            pattern_table.add_row(pattern, str(count))

        console.print(pattern_table)


def _show_detailed_results(result) -> None:
    """Show detailed parse results in tables."""
    # Subjects table
    if result.subjects:
        subjects_table = Table(title="Subjects")
        subjects_table.add_column("Subject", style="cyan", max_width=40)
        subjects_table.add_column("Sheet", style="blue")
        subjects_table.add_column("Pattern", style="magenta")
        subjects_table.add_column("Lec", style="green")
        subjects_table.add_column("Prac", style="yellow")
        subjects_table.add_column("Lab", style="red")

        for subject in result.subjects[:20]:  # Limit to first 20
            subjects_table.add_row(
                subject.subject[:40],
                subject.sheet,
                subject.pattern,
                str(len(subject.lecture_streams)),
                str(len(subject.practical_streams)),
                str(len(subject.lab_streams)),
            )

        if len(result.subjects) > 20:
            subjects_table.add_row("...", "...", "...", "...", "...", "...")

        console.print(subjects_table)


# Default paths for reference data
DEFAULT_ROOMS_CSV = Path("data/reference/rooms.csv")
DEFAULT_SUBJECT_ROOMS_JSON = Path("data/reference/subject-rooms.json")
DEFAULT_INSTRUCTOR_ROOMS_JSON = Path("data/reference/instructor-rooms.json")
DEFAULT_GROUP_BUILDINGS_JSON = Path("data/reference/group-buildings.json")
DEFAULT_INSTRUCTOR_AVAILABILITY_JSON = Path("data/reference/instructor-availability.json")


@app.command()
def schedule(
    input_file: Annotated[
        Path,
        typer.Argument(help="Parsed JSON file from form1-parser parse command"),
    ],
    output: Annotated[
        Optional[Path],
        typer.Option("-o", "--output", help="Output JSON file path"),
    ] = None,
    rooms_csv: Annotated[
        Optional[Path],
        typer.Option("--rooms", help="Path to rooms.csv file"),
    ] = None,
    subject_rooms: Annotated[
        Optional[Path],
        typer.Option("--subject-rooms", help="Path to subject-rooms.json file"),
    ] = None,
    instructor_rooms: Annotated[
        Optional[Path],
        typer.Option("--instructor-rooms", help="Path to instructor-rooms.json file"),
    ] = None,
    group_buildings: Annotated[
        Optional[Path],
        typer.Option("--group-buildings", help="Path to group-buildings.json file"),
    ] = None,
    instructor_availability: Annotated[
        Optional[Path],
        typer.Option("--instructor-availability", help="Path to instructor-availability.json file"),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show detailed output"),
    ] = False,
) -> None:
    """Generate Stage 1 schedule for multi-group lectures."""
    if not input_file.exists():
        console.print(f"[bold red]Error:[/bold red] File not found: {input_file}")
        raise typer.Exit(1)

    # Use default paths if not provided
    rooms_path = rooms_csv or DEFAULT_ROOMS_CSV
    subject_rooms_path = subject_rooms or DEFAULT_SUBJECT_ROOMS_JSON
    instructor_rooms_path = instructor_rooms or DEFAULT_INSTRUCTOR_ROOMS_JSON
    group_buildings_path = group_buildings or DEFAULT_GROUP_BUILDINGS_JSON
    instructor_availability_path = instructor_availability or DEFAULT_INSTRUCTOR_AVAILABILITY_JSON

    # Validate rooms.csv exists
    if not rooms_path.exists():
        console.print(f"[bold red]Error:[/bold red] Rooms file not found: {rooms_path}")
        raise typer.Exit(1)

    with console.status("[bold green]Loading parsed data..."):
        data = load_parsed_data(input_file)

    streams = data.get("streams", [])
    if not streams:
        console.print("[bold yellow]Warning:[/bold yellow] No streams found in input file")
        raise typer.Exit(1)

    console.print(f"\n[bold]Schedule Generation for:[/bold] {input_file.name}")
    console.print(f"  Total streams in input: {len(streams)}")

    with console.status("[bold green]Creating schedule..."):
        scheduler = create_scheduler(
            rooms_path,
            subject_rooms_path if subject_rooms_path.exists() else None,
            instructor_rooms_path if instructor_rooms_path.exists() else None,
            group_buildings_path if group_buildings_path.exists() else None,
            instructor_availability_path if instructor_availability_path.exists() else None,
        )
        result = scheduler.schedule(streams)

    # Show summary
    console.print(f"\n[bold]Stage 1 Schedule Results:[/bold]")
    console.print(f"  Total assignments: {result.total_assigned}")
    console.print(f"  Unscheduled streams: {result.total_unscheduled}")

    # Show statistics
    if result.statistics.by_day:
        console.print(f"\n[bold]Distribution by day:[/bold]")
        for day, count in sorted(result.statistics.by_day.items()):
            console.print(f"  {day.capitalize()}: {count}")

    if result.statistics.by_shift:
        console.print(f"\n[bold]Distribution by shift:[/bold]")
        for shift, count in sorted(result.statistics.by_shift.items()):
            console.print(f"  {shift.capitalize()}: {count}")

    if verbose and result.statistics.room_utilization:
        console.print(f"\n[bold]Room utilization by address:[/bold]")
        for address, count in sorted(
            result.statistics.room_utilization.items(), key=lambda x: -x[1]
        ):
            console.print(f"  {address}: {count}")

    if verbose and result.unscheduled_stream_ids:
        console.print(f"\n[bold yellow]Unscheduled streams ({len(result.unscheduled_stream_ids)}):[/bold yellow]")
        for stream_id in result.unscheduled_stream_ids[:10]:
            console.print(f"  [yellow]- {stream_id}[/yellow]")
        if len(result.unscheduled_stream_ids) > 10:
            console.print(f"  [yellow]... and {len(result.unscheduled_stream_ids) - 10} more[/yellow]")

    # Export if output path provided
    if output:
        output_path = output if output.suffix == ".json" else output.with_suffix(".json")
        with console.status(f"[bold green]Exporting to {output_path}..."):
            export_schedule_json(result, output_path)
        console.print(f"\n[bold green]✓[/bold green] Schedule exported to: {output_path}")
    else:
        # Default output path
        default_output = Path("output/schedule.json")
        with console.status(f"[bold green]Exporting to {default_output}..."):
            export_schedule_json(result, default_output)
        console.print(f"\n[bold green]✓[/bold green] Schedule exported to: {default_output}")


@app.command("generate-excel")
def generate_excel(
    input_file: Annotated[
        Path,
        typer.Argument(help="Schedule JSON file"),
    ],
    output_dir: Annotated[
        Optional[Path],
        typer.Option("-o", "--output", help="Output directory for Excel files"),
    ] = None,
    language: Annotated[
        Optional[str],
        typer.Option("--language", "-l", help="Language filter: 'kaz' or 'rus'"),
    ] = None,
    year: Annotated[
        Optional[int],
        typer.Option("--year", "-y", help="Year filter: 1, 2, 3, or 4"),
    ] = None,
    week_type: Annotated[
        Optional[str],
        typer.Option("--week-type", "-w", help="Week type filter: 'odd' or 'even'"),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show detailed output"),
    ] = False,
) -> None:
    """Generate Excel schedule files from schedule JSON."""
    if not input_file.exists():
        console.print(f"[bold red]Error:[/bold red] File not found: {input_file}")
        raise typer.Exit(1)

    # Validate language option
    if language and language not in ("kaz", "rus"):
        console.print(f"[bold red]Error:[/bold red] Invalid language: {language}. Use 'kaz' or 'rus'.")
        raise typer.Exit(1)

    # Validate year option
    if year and year not in (1, 2, 3, 4):
        console.print(f"[bold red]Error:[/bold red] Invalid year: {year}. Use 1, 2, 3, or 4.")
        raise typer.Exit(1)

    # Validate week_type option
    if week_type and week_type not in ("odd", "even"):
        console.print(f"[bold red]Error:[/bold red] Invalid week type: {week_type}. Use 'odd' or 'even'.")
        raise typer.Exit(1)

    # Default output directory
    output_path = output_dir or Path("output/excel")

    console.print(f"\n[bold]Generating Excel schedules from:[/bold] {input_file.name}")
    if language:
        console.print(f"  Language: {language}")
    if year:
        console.print(f"  Year: {year}")
    if week_type:
        console.print(f"  Week type: {week_type}")

    with console.status("[bold green]Generating Excel files..."):
        generated_files = generate_schedule_excel(
            input_path=input_file,
            output_dir=output_path,
            language=language,
            year=year,
            week_type=week_type,
        )

    if not generated_files:
        console.print("[bold yellow]Warning:[/bold yellow] No files generated. No groups matched the criteria.")
        raise typer.Exit(1)

    console.print(f"\n[bold green]✓[/bold green] Generated {len(generated_files)} file(s):")
    for file_path in generated_files:
        console.print(f"  - {file_path}")

    if verbose:
        console.print(f"\n[bold]Output directory:[/bold] {output_path.absolute()}")


if __name__ == "__main__":
    app()
