from __future__ import annotations

import asyncio
import typer
from rich.console import Console
from pathlib import Path

from agent import generate_audit_report, generate_audit_report_multi, GenerateAuditOptions

import os


console = Console()  # initialize Rich console for pretty printing
app = typer.Typer(add_completion=False)  # initialize Typer app for CLI, no cmd completion


@app.callback(invoke_without_command=True)
def run(
    inputs: list[str] = typer.Option(
        ..., "--input", "-i", help="Input files (repeatable): PDF/DOCX/XLSX/Image. e.g. -i a.pdf -i b.docx"
    ),
    output: str = typer.Option(..., "--output", "-o", help="Output markdown file"),
    model: str = typer.Option("gpt-5", "--model", help="Copilot model name"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
    prompt_template: str = typer.Option(None, "--prompt-template", help="Prompt template id"),
    prompt_text: str = typer.Option(None, "--prompt", help="Custom prompt text"),
    prompt_file: str = typer.Option(None, "--prompt-file", help="Path to custom prompt file"),
):
    """Audit documents and generate a governance audit assessment report (Markdown)."""
    try:
        # Load prompt from file if provided
        prompt_override = None
        if prompt_text:
            prompt_override = prompt_text
        elif prompt_file:
            prompt_path = Path(prompt_file)
            if prompt_path.exists():
                prompt_override = prompt_path.read_text(encoding="utf-8")
            else:
                raise ValueError(f"Prompt file not found: {prompt_file}")
        
        # Create options with prompt info
        options = GenerateAuditOptions(
            model=model,
            verbose=verbose,
            prompt_text=prompt_override,
            prompt_template_id=prompt_template,
        )
        
        # Support both single and multiple files
        if len(inputs) == 1:
            asyncio.run(
                generate_audit_report(
                    input_file=inputs[0],
                    output_file=output,
                    options=options,
                )
            )
        else:
            asyncio.run(
                generate_audit_report_multi(
                    input_files=inputs,
                    output_file=output,
                    options=options,
                )
            )
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


def main() -> None:
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")
    if hasattr(__import__('sys').stdout, "reconfigure"):
        __import__('sys').stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(__import__('sys').stderr, "reconfigure"):
        __import__('sys').stderr.reconfigure(encoding="utf-8", errors="replace")
    # package entry point: Typer will handle command-line parsing and invoke the `run` function
    app()

    
if __name__ == "__main__":
    app()
