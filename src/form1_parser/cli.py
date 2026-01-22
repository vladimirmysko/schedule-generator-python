"""CLI entry point for Form-1 parser."""

from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from .exporters import get_exporter
from .parser import Form1Parser

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


if __name__ == "__main__":
    app()
