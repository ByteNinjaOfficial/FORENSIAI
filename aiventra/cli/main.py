"""Typer CLI for AIVENTRA autopsy report analysis."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(
    name="aiventra",
    help="AIVENTRA — AI-Powered Forensic Triage & Postmortem Intelligence System",
)


def _setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


@app.command()
def analyze(
    pdf_path: Path = typer.Argument(..., exists=True, help="Path to the PDF autopsy report"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path (JSON)"),
    no_redact: bool = typer.Option(False, "--no-redact", help="Disable PII redaction"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Override LLM model name"),
    temperature: Optional[float] = typer.Option(None, "--temperature", "-t", help="Override LLM temperature"),
    max_tokens: Optional[int] = typer.Option(None, "--max-tokens", help="Override max output tokens"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Only output JSON result"),
):
    """Analyze an autopsy report PDF and extract structured forensic findings."""
    _setup_logging(verbose)

    if quiet:
        logging.getLogger().setLevel(logging.ERROR)

    from aiventra.core.pipeline import run_pipeline

    try:
        result = run_pipeline(
            pdf_path=pdf_path,
            redact_pii=not no_redact,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except FileNotFoundError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)
    except EnvironmentError as exc:
        typer.echo(f"Configuration error: {exc}", err=True)
        raise typer.Exit(code=1)
    except RuntimeError as exc:
        typer.echo(f"Extraction error: {exc}", err=True)
        raise typer.Exit(code=1)

    output_json = result.model_dump_json(indent=2)

    if output:
        output.write_text(output_json)
        if not quiet:
            typer.echo(f"Results written to: {output}")
    else:
        typer.echo(output_json)

    if not quiet:
        ext = result.extraction
        typer.echo("", err=True)
        typer.echo("=== EXTRACTION SUMMARY ===", err=True)
        typer.echo(f"  Cause of death: {ext.cause_of_death or 'NOT FOUND'}", err=True)
        typer.echo(f"  Manner of death: {ext.manner_of_death.value if ext.manner_of_death else 'NOT FOUND'}", err=True)
        typer.echo(f"  Confidence: {ext.extraction_confidence:.2f}", err=True)
        typer.echo(f"  Injuries: {len(ext.injury_patterns)}", err=True)
        typer.echo(f"  Toxicology findings: {len(ext.toxicology_findings)}", err=True)
        typer.echo(f"  Validation: {'PASSED' if result.validation.is_valid else 'FLAGGED'}", err=True)
        if result.validation.flags:
            typer.echo("  Flags:", err=True)
            for flag in result.validation.flags:
                typer.echo(f"    - {flag}", err=True)
        typer.echo(f"  Model: {result.model_used}", err=True)
        typer.echo(f"  Processing time: {result.processing_time_seconds:.2f}s", err=True)


@app.command()
def check():
    """Verify that configuration and dependencies are in place."""
    from aiventra.core.config import Config

    issues = []

    try:
        Config.validate()
        typer.echo("OK  API key configured")
    except EnvironmentError as exc:
        typer.echo(f"MISSING  {exc}")
        issues.append("api_key")

    try:
        import pdfplumber
        typer.echo("OK  pdfplumber installed")
    except ImportError:
        typer.echo("MISSING  pdfplumber not installed")
        issues.append("pdfplumber")

    try:
        import fitz
        typer.echo("OK  PyMuPDF installed")
    except ImportError:
        typer.echo("OPTIONAL  PyMuPDF not installed (OCR fallback unavailable)")
        issues.append("pymupdf")

    try:
        import pytesseract
        typer.echo("OK  pytesseract installed")
    except ImportError:
        typer.echo("OPTIONAL  pytesseract not installed (OCR fallback unavailable)")
        issues.append("pytesseract")

    try:
        from openai import OpenAI
        typer.echo("OK  openai installed")
    except ImportError:
        typer.echo("MISSING  openai not installed")
        issues.append("openai")

    if not issues:
        typer.echo("\nAll checks passed!")
    else:
        typer.echo(f"\n{len(issues)} issue(s) found. Run: pip install -r requirements.txt")


def main():
    app()


if __name__ == "__main__":
    main()