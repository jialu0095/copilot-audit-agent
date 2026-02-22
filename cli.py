from __future__ import annotations

import asyncio
import typer
from rich.console import Console

from agent import generate_audit_report, GenerateAuditOptions

console = Console()  # initialize Rich console for pretty printing
app = typer.Typer(add_completion=False)  # initialize Typer app for CLI, no cmd completion


@app.callback(invoke_without_command=True)
def run(
    input: str = typer.Option(..., "--input", "-i", help="Input file: PDF/DOCX/XLSX/Image"),
    output: str = typer.Option(..., "--output", "-o", help="Output markdown file"),
    model: str = typer.Option("gpt-5", "--model", help="Copilot model name"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
):
    """Audit a document and generate a governance audit assessment report (Markdown)."""
    try:
        asyncio.run(
            generate_audit_report(
                input_file=input,
                output_file=output,
                options=GenerateAuditOptions(model=model, verbose=verbose),
            )
        )
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


def main() -> None:
    # package entry point: Typer will handle command-line parsing and invoke the `run` function
    app()