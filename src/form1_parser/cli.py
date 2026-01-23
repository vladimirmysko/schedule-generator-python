"""CLI entry point for Form-1 parser."""

import json
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from .exporters import get_exporter
from .parser import Form1Parser
from .scheduler import ORToolsScheduler, WeekType

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
        typer.Argument(
            help="Path to the Form-1 Excel file", exists=True, readable=True
        ),
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
        console.print(
            f"\n[bold yellow]Warnings ({len(result.warnings)}):[/bold yellow]"
        )
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
        console.print(
            f"\n  [yellow]Sheets missing: {len(validation['sheets_missing'])}[/yellow]"
        )
        console.print(f"    {', '.join(validation['sheets_missing'])}")

    if validation["errors"]:
        console.print(f"\n[bold red]Errors ({len(validation['errors'])}):[/bold red]")
        for error in validation["errors"]:
            console.print(f"  [red]• {error}[/red]")

    if validation["warnings"]:
        console.print(
            f"\n[bold yellow]Warnings ({len(validation['warnings'])}):[/bold yellow]"
        )
        for warning in validation["warnings"]:
            console.print(f"  [yellow]• {warning}[/yellow]")

    if not validation["valid"]:
        raise typer.Exit(1)


@app.command()
def stats(
    input_file: Annotated[
        Path,
        typer.Argument(
            help="Path to the Form-1 Excel file", exists=True, readable=True
        ),
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


@app.command()
def schedule(
    input_file: Annotated[
        Path,
        typer.Argument(
            help="Path to parsed result JSON file", exists=True, readable=True
        ),
    ],
    output: Annotated[
        Optional[Path],
        typer.Option("-o", "--output", help="Output JSON file path"),
    ] = None,
    time_limit: Annotated[
        int,
        typer.Option("--time-limit", "-t", help="Solver time limit in seconds"),
    ] = 300,
    config_dir: Annotated[
        Optional[Path],
        typer.Option("--config", "-c", help="Configuration directory"),
    ] = None,
    week_type: Annotated[
        str,
        typer.Option("--week", "-w", help="Week type: odd, even, or both"),
    ] = "both",
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show detailed output"),
    ] = False,
) -> None:
    """Generate schedule from parsed Form-1 data using CP-SAT solver."""
    # Load input data
    with console.status("[bold green]Loading parsed data..."):
        with open(input_file, encoding="utf-8") as f:
            data = json.load(f)

    # Extract streams from subjects
    streams = []
    for subject in data.get("subjects", []):
        streams.extend(subject.get("lecture_streams", []))
        streams.extend(subject.get("practical_streams", []))
        streams.extend(subject.get("lab_streams", []))

    console.print(f"\n[bold]Scheduling from:[/bold] {input_file.name}")
    console.print(f"  Total streams loaded: {len(streams)}")

    # Parse week type
    week_type_enum = WeekType(week_type.lower())

    # Determine config directory
    if config_dir is None:
        config_dir = Path("reference")

    # Create scheduler
    scheduler = ORToolsScheduler(config_dir, time_limit)

    # Run scheduling
    with console.status(f"[bold green]Scheduling (time limit: {time_limit}s)..."):
        result = scheduler.schedule(streams, week_type=week_type_enum)

    # Show results
    console.print("\n[bold]Scheduling Results:[/bold]")

    stats = result.statistics
    rate = stats.total_assigned / stats.total_streams * 100 if stats.total_streams > 0 else 0

    results_table = Table(show_header=False)
    results_table.add_column("Metric", style="cyan")
    results_table.add_column("Value", style="green")

    results_table.add_row("Total Streams", str(stats.total_streams))
    results_table.add_row("Scheduled", str(stats.total_assigned))
    results_table.add_row("Unscheduled", str(stats.total_unscheduled))
    results_table.add_row("Success Rate", f"{rate:.1f}%")
    results_table.add_row("Solver Time", f"{stats.solver_time_seconds:.2f}s")

    console.print(results_table)

    # Show by day distribution
    if stats.by_day:
        day_table = Table(title="Assignments by Day")
        day_table.add_column("Day", style="cyan")
        day_table.add_column("Count", style="green")

        for day, count in sorted(stats.by_day.items()):
            day_table.add_row(day.capitalize(), str(count))

        console.print(day_table)

    # Show unscheduled reasons if verbose
    if verbose and result.unscheduled_streams:
        console.print(f"\n[bold yellow]Unscheduled Streams ({len(result.unscheduled_streams)}):[/bold yellow]")

        # Group by reason
        by_reason: dict[str, int] = {}
        for us in result.unscheduled_streams:
            reason = us.reason.value
            by_reason[reason] = by_reason.get(reason, 0) + 1

        for reason, count in sorted(by_reason.items(), key=lambda x: -x[1]):
            console.print(f"  {reason}: {count}")

    # Export if output path provided
    if output:
        if not output.suffix:
            output = output.with_suffix(".json")

        output.parent.mkdir(parents=True, exist_ok=True)

        with open(output, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

        console.print(f"\n[bold green]✓[/bold green] Schedule saved to: {output}")


@app.command(name="generate-excel")
def generate_excel(
    input_file: Annotated[
        Path,
        typer.Argument(
            help="Path to schedule JSON file", exists=True, readable=True
        ),
    ],
    output_dir: Annotated[
        Optional[Path],
        typer.Option("-o", "--output", help="Output directory for Excel files"),
    ] = None,
) -> None:
    """Generate Excel schedule files from schedule JSON."""
    # Load schedule data
    with console.status("[bold green]Loading schedule data..."):
        with open(input_file, encoding="utf-8") as f:
            data = json.load(f)

    assignments = data.get("assignments", [])
    console.print(f"\n[bold]Generating Excel from:[/bold] {input_file.name}")
    console.print(f"  Total assignments: {len(assignments)}")

    if output_dir is None:
        output_dir = Path("output/excel")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate Excel files
    from .scheduler.excel_generator import generate_schedule_excel

    with console.status("[bold green]Generating Excel files..."):
        generated_files = generate_schedule_excel(
            input_path=input_file,
            output_dir=output_dir,
        )

    console.print(f"\n[bold green]✓[/bold green] Generated {len(generated_files)} Excel files:")
    for file_path in generated_files[:10]:
        console.print(f"  {file_path.name}")

    if len(generated_files) > 10:
        console.print(f"  ... and {len(generated_files) - 10} more")


if __name__ == "__main__":
    app()
