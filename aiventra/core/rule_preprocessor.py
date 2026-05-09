"""Rule-based preprocessing for autopsy report text.

Splits raw text into named sections, redacts PII, and normalizes measurements/dates
before sending to the LLM. This reduces token usage and protects sensitive data.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Tuple

from aiventra.core.schemas import PreprocessedDocument, SectionContent

logger = logging.getLogger(__name__)

AUTOPSY_SECTIONS = [
    "external examination",
    "internal examination",
    "cardiovascular system",
    "respiratory system",
    "central nervous system",
    "gastrointestinal system",
    "hepatobiliary system",
    "genitourinary system",
    "endocrine system",
    "musculoskeletal system",
    "toxicology",
    "histopathology",
    "microscopic examination",
    "cause of death",
    "manner of death",
    "opinion",
    "summary",
    "diagnosis",
    "findings",
    "clinical summary",
    "circumstances of death",
    "identification",
    "demographics",
    "evidence of injury",
    "medical history",
]

CRIME_SCENE_SECTIONS = [
    "incident report",
    "crime scene report",
    "summary report of scene",
    "primary body examination",
    "evidence collected on body",
    "opinions",
    "apparent manner of death",
    "apparent cause of death",
    "crime scene investigation",
    "crime scene floorplan",
    "inventory of evidence",
    "inventory of evidence collected at the crime scene",
    "remarks",
    "reporting officers' narrative",
    "reporting officers narrative",
    "narrative",
]

ALL_SECTIONS = list(dict.fromkeys(AUTOPSY_SECTIONS + CRIME_SCENE_SECTIONS))

DOCUMENT_TYPE_KEYWORDS = {
    "autopsy": ["autopsy", "postmortem", "post-mortem", "pathology report", "medical examiner"],
    "crime_scene": ["crime scene", "investigation report", "csi", "evidence collected", "incident report"],
}

PII_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("social_security", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("hkid", re.compile(r"\b[A-Z]\d(?:\d{4,5}|[A-Z]{4,6})\([A-Z0-9]\)")),
    ("phone", re.compile(r"\b\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")),
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("date_of_birth", re.compile(r"(?i)(date\s+of\s+birth|dob)[:\s]+\d{1,2}[/-]\d{1,2}[/-]\d{2,4}")),
    ("address", re.compile(r"(?i)\d+\s+[A-Za-z\s]+(?:street|st|avenue|ave|boulevard|blvd|road|rd|drive|dr|lane|ln|court|ct|way)\.?\s*,?\s*[A-Za-z\s]+,?\s*[A-Z]{2}\s+\d{5}")),
    ("mrn", re.compile(r"(?i)(medical\s+record\s+number|mrn)[:\s]+[\w-]+")),
    ("case_number", re.compile(r"(?i)(case\s+(?:number|no\.?|#)|file\s+number)\.?\s*:\s*[\w-]+")),
    ("officer_id", re.compile(r"\b(?:P|D)\d{5,8}\b")),
    ("person_name_title", re.compile(r"\b(?i:dr|mr|mrs|ms)\.\s+(?:[A-Z][a-z]+|[A-Z]{2,})(?:\s+[A-Z][a-z]+)?(?=\s|$|,|;|\.)")),
]


def detect_document_type(text: str) -> str:
    """Detect whether the document is an autopsy report or crime scene report."""
    text_lower = text.lower()
    scores: Dict[str, int] = {doc_type: 0 for doc_type in DOCUMENT_TYPE_KEYWORDS}
    for doc_type, keywords in DOCUMENT_TYPE_KEYWORDS.items():
        for keyword in keywords:
            scores[doc_type] += text_lower.count(keyword)
    if not any(scores.values()):
        return "unknown"
    return max(scores, key=lambda k: scores[k])


def _normalize_unicode(text: str) -> str:
    """Normalize Unicode characters for consistent matching."""
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    return text


def detect_sections(text: str) -> List[SectionContent]:
    """Split document text into named sections based on common forensic report headers."""
    text = _normalize_unicode(text)
    lines = text.split("\n")
    sections: List[SectionContent] = []
    current_name: Optional[str] = None
    current_lines: List[str] = []
    current_page = 1
    current_paragraph = 1

    section_pattern = re.compile(
        r"^\s*(?:\d+\.?\s+)?(" + "|".join(re.escape(s) for s in ALL_SECTIONS) + r")\s*[:\-]?\s*$",
        re.IGNORECASE,
    )

    inline_section_pattern = re.compile(
        r"(?:^|\n)\s*(" + "|".join(re.escape(s) for s in ALL_SECTIONS) + r")\s*:\s*",
        re.IGNORECASE,
    )

    page_header = re.compile(r"^---\s*Page\s+(\d+)(?:\s+\(OCR\))?\s*---$")

    def flush():
        if current_name and current_lines:
            content = "\n".join(current_lines).strip()
            if content:
                sections.append(
                    SectionContent(
                        name=current_name,
                        content=content,
                        page_number=current_page,
                        start_paragraph=current_paragraph,
                    )
                )

    for line in lines:
        page_match = page_header.match(line)
        if page_match:
            flush()
            current_page = int(page_match.group(1))
            current_paragraph = 1
            current_lines = []
            continue

        sec_match = section_pattern.match(line)
        if sec_match:
            flush()
            current_name = sec_match.group(1).strip().lower()
            current_lines = []
            current_paragraph += 1
            continue

        inline_match = inline_section_pattern.search(line)
        if inline_match and not current_name:
            flush()
            current_name = inline_match.group(1).strip().lower()
            remainder = line[inline_match.end():].strip()
            if remainder:
                current_lines = [remainder]
            current_paragraph += 1
            continue

        current_lines.append(line)

    flush()
    logger.info("Detected %d sections in document", len(sections))
    return sections


def redact_pii(text: str) -> Tuple[str, List[str]]:
    """Redact personally identifiable information from text.

    Returns:
        Tuple of (redacted_text, list_of_redacted_field_names)
    """
    redacted = text
    redacted_fields: List[str] = []

    for field_name, pattern in PII_PATTERNS:
        matches = pattern.findall(redacted)
        if matches:
            redacted_fields.append(field_name)
            redacted = pattern.sub(f"[REDACTED_{field_name.upper()}]", redacted)

    logger.info("Redacted %d PII field types: %s", len(redacted_fields), redacted_fields)
    return redacted, redacted_fields


def normalize_measurements(text: str) -> str:
    """Normalize measurement formats for consistent LLM parsing."""
    text = re.sub(r"(\d+)\s*cm\b", r"\1 cm", text, flags=re.IGNORECASE)
    text = re.sub(r"(\d+)\s*mm\b", r"\1 mm", text, flags=re.IGNORECASE)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*kg\b", r"\1 kg", text, flags=re.IGNORECASE)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*g\b", r"\1 g", text, flags=re.IGNORECASE)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*lb[s]?\b", r"\1 lbs", text, flags=re.IGNORECASE)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*mcg\b", r"\1 µg", text, flags=re.IGNORECASE)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*µg\b", r"\1 µg", text, flags=re.IGNORECASE)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*mg\b", r"\1 mg", text, flags=re.IGNORECASE)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*ng\b", r"\1 ng", text, flags=re.IGNORECASE)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*ml\b", r"\1 mL", text, flags=re.IGNORECASE)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*dl\b", r"\1 dL", text, flags=re.IGNORECASE)
    return text


def normalize_dates(text: str) -> str:
    """Normalize date formats to ISO 8601 (YYYY-MM-DD) where possible."""
    text = re.sub(
        r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b",
        lambda m: f"{m.group(3)}-{m.group(1).zfill(2)}-{m.group(2).zfill(2)}",
        text,
    )
    text = re.sub(
        r"\b(\d{1,2})-(\d{1,2})-(\d{4})\b",
        lambda m: f"{m.group(3)}-{m.group(1).zfill(2)}-{m.group(2).zfill(2)}",
        text,
    )
    return text


def preprocess(
    raw_text: str,
    tables: List[dict],
    page_count: int,
    redact: bool = True,
) -> PreprocessedDocument:
    """Full preprocessing pipeline: normalize → redact → section detection.

    Args:
        raw_text: Raw extracted text from pdf_parser.
        tables: Extracted table data.
        page_count: Total pages in the document.
        redact: Whether to redact PII (default True).

    Returns:
        PreprocessedDocument with sections, redaction info, and normalized text.
    """
    text = normalize_measurements(raw_text)
    text = normalize_dates(text)

    redacted_fields: List[str] = []
    if redact:
        text, redacted_fields = redact_pii(text)

    sections = detect_sections(text)

    doc_type = detect_document_type(text)

    return PreprocessedDocument(
        raw_text=text,
        sections=sections,
        page_count=page_count,
        tables=tables,
        redacted_fields=redacted_fields,
        document_type=doc_type,
    )