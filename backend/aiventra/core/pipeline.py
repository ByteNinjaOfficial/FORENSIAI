"""Pipeline orchestrator — ties together PDF parsing, preprocessing, extraction, and validation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from aiventra.core.llm_extractor import extract_findings
from aiventra.core.pdf_parser import extract_text
from aiventra.core.rule_preprocessor import preprocess
from aiventra.core.schemas import AutopsyExtraction, ExtractionResult
from aiventra.core.validator import validate

logger = logging.getLogger(__name__)


def run_pipeline(
    pdf_path: Path,
    redact_pii: bool = True,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> ExtractionResult:
    """Full autopsy report analysis pipeline.

    Args:
        pdf_path: Path to the PDF autopsy report.
        redact_pii: Whether to redact PII before LLM call (default True).
        model: Override LLM model name.
        temperature: Override LLM temperature.
        max_tokens: Override LLM max tokens.

    Returns:
        ExtractionResult with extraction, validation, preprocessed doc, and metadata.
    """
    logger.info("Starting pipeline for: %s", pdf_path)

    raw_text, tables, page_count = extract_text(pdf_path)
    logger.info("PDF parsed: %d pages, %d tables", page_count, len(tables))

    doc = preprocess(raw_text, tables, page_count, redact=redact_pii)
    logger.info("Preprocessed: %d sections, %d redacted fields", len(doc.sections), len(doc.redacted_fields))

    extraction, model_used, elapsed = extract_findings(
        doc, model=model, temperature=temperature, max_tokens=max_tokens
    )
    logger.info("LLM extraction done: model=%s, %.2fs", model_used, elapsed)

    validation_result = validate(extraction, doc)
    logger.info(
        "Validation: valid=%s, flags=%d, confidence_adjustment=%.2f",
        validation_result.is_valid,
        len(validation_result.flags),
        validation_result.confidence_adjustment,
    )

    extraction.extraction_confidence += validation_result.confidence_adjustment
    extraction.extraction_confidence = max(0.0, min(1.0, extraction.extraction_confidence))
    extraction.validation_flags = validation_result.flags

    return ExtractionResult(
        extraction=extraction,
        validation=validation_result,
        preprocessed=doc,
        model_used=model_used,
        processing_time_seconds=elapsed,
    )