"""LLM-based forensic extraction using DeepSeek via Featherless API.

Sends preprocessed autopsy report text to the LLM with a structured extraction
prompt and parses the JSON response into AutopsyExtraction models.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Optional

from openai import OpenAI

from aiventra.core.config import Config
from aiventra.core.schemas import AutopsyExtraction, InjuryObservation, MannerOfDeath, PreprocessedDocument

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = """You are a forensic pathology expert assistant. Your task is to extract structured forensic findings from autopsy and crime scene reports.

CRITICAL RULES:
1. Extract ONLY information that is explicitly stated in the text. Do NOT infer, guess, or fabricate any findings.
2. If information is not present or unclear, use null for optional fields.
3. For each extracted field, provide the source location in the document (page and section).
4. Assess extraction confidence based on how clearly the information is stated.
5. This is an ADVISORY system — all outputs support human decision-making and are not conclusive.
6. Return valid JSON only. No markdown, no code fences, no commentary outside the JSON.

EXTRACTION GUIDELINES:
- Extract ALL injuries mentioned, even if brief (e.g., "obvious external injuries, 1 to his head and another to his abdomen" = 2 injuries).
- Extract contributing factors from Opinions, Remarks, or narrative sections (e.g., "peritonitis", "internal bleeding").
- For crime scene reports, extract from "Primary Body Examination", "Opinions", "Apparent Cause/Manner of Death" sections.
- If the document mentions multiple victims, note this in medical_observations and extract findings for the primary victim.
- Extract weapon information from evidence/narrative sections and include in injury descriptions.
- Note any evidence items (weapons, fingerprints, footprints) in medical_observations.

You must return a JSON object matching this schema:
{
  "case_identifier": "string or null",
  "date_of_exam": "YYYY-MM-DD or null",
  "date_of_death": "YYYY-MM-DD or null",
  "cause_of_death": "string or null — the primary cause as stated in the report",
  "manner_of_death": "natural|accident|homicide|suicide|undetermined|pending|null",
  "certainty": "confirmed|probable|possible|undetermined",
  "contributing_factors": ["string — e.g. peritonitis, internal bleeding, infection"],
  "injury_patterns": [
    {
      "description": "string — include weapon and wound dimensions if stated",
      "body_region": "string",
      "injury_type": "string",
      "severity": "string or null",
      "source_location": "page X, section Y"
    }
  ],
  "medical_observations": ["string — significant medical findings, evidence items, multiple victim notes"],
  "toxicology_findings": [
    {
      "substance": "string",
      "concentration": "string or null",
      "unit": "string or null",
      "significance": "therapeutic|elevated|toxic|lethal|not significant|null",
      "source_location": "page X, section Y"
    }
  ],
  "postmortem_interval_estimate": "string or null",
  "extraction_confidence": 0.0-1.0,
  "source_references": {
    "cause_of_death": "page X, section Y",
    "manner_of_death": "page X, section Y"
  }
}"""


def _build_user_prompt(doc: PreprocessedDocument) -> str:
    sections_text = ""
    if doc.sections:
        for sec in doc.sections:
            sections_text += f"\n## {sec.name.upper()} (Page {sec.page_number})\n{sec.content}\n"
    else:
        sections_text = doc.raw_text

    tables_text = ""
    if doc.tables:
        tables_text = "\n\n--- EXTRACTED TABLES ---\n"
        for i, table in enumerate(doc.tables, 1):
            tables_text += f"\nTable {i}:\n"
            for key, value in table.items():
                if value:
                    tables_text += f"  {key}: {value}\n"

    redaction_note = ""
    if doc.redacted_fields:
        redaction_note = (
            f"\nNOTE: The following PII fields have been redacted: {', '.join(doc.redacted_fields)}. "
            "Do not attempt to reconstruct redacted values."
        )

    doc_type_label = "autopsy report"
    if hasattr(doc, "document_type") and doc.document_type:
        doc_type_label = {
            "autopsy": "autopsy report",
            "crime_scene": "crime scene investigation report",
        }.get(doc.document_type, "forensic report")

    return (
        f"Analyze the following {doc_type_label} and extract structured forensic findings.{redaction_note}\n"
        f"\n--- {doc_type_label.upper()} ---\n{sections_text}\n{tables_text}\n"
        f"--- END OF REPORT ---\n\n"
        f"Extract all forensic findings as structured JSON per the schema. "
        f"Remember: extract ONLY what is explicitly stated. Do not fabricate findings. "
        f"Extract ALL injuries and contributing factors mentioned, even if briefly stated."
    )


def extract_findings(
    doc: PreprocessedDocument,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> tuple[AutopsyExtraction, str, float]:
    """Run LLM extraction on a preprocessed autopsy document.

    Args:
        doc: Preprocessed autopsy report document.
        model: Override the default model name.
        temperature: Override the default temperature.
        max_tokens: Override the default max tokens.

    Returns:
        Tuple of (AutopsyExtraction, model_used, elapsed_seconds)

    Raises:
        EnvironmentError: If API key is not configured.
        RuntimeError: If LLM returns invalid or unparsable output.
    """
    start = time.time()
    try:
        Config.validate()
    except EnvironmentError as exc:
        logger.warning("LLM unavailable: %s. Using rule-based fallback extraction.", exc)
        return _fallback_extract_findings(doc, "rule-based-fallback", time.time() - start)

    client = OpenAI(
        api_key=Config.API_KEY,
        base_url=Config.API_BASE_URL,
    )

    model_name = model or Config.MODEL_NAME
    temp = temperature if temperature is not None else Config.LLM_TEMPERATURE
    max_tok = max_tokens or Config.LLM_MAX_TOKENS

    user_prompt = _build_user_prompt(doc)

    logger.info(
        "Calling LLM: model=%s, temperature=%.2f, max_tokens=%d, prompt_length=%d",
        model_name, temp, max_tok, len(user_prompt),
    )

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temp,
            max_tokens=max_tok,
        )
        elapsed = time.time() - start
    except Exception as exc:
        elapsed = time.time() - start
        logger.warning(
            "LLM request failed after %.2fs: %s. Using rule-based fallback extraction.",
            elapsed,
            exc,
        )
        return _fallback_extract_findings(doc, f"{model_name}+rule-fallback", elapsed)

    raw_content = response.choices[0].message.content or ""
    logger.info("LLM responded in %.2fs, %d characters", elapsed, len(raw_content))

    try:
        cleaned = raw_content.strip()
        if cleaned.startswith("```"):
            first_newline = cleaned.index("\n")
            last_fence = cleaned.rfind("```")
            cleaned = cleaned[first_newline + 1 : last_fence].strip()

        data = json.loads(cleaned)
        extraction = AutopsyExtraction(**data)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("Failed to parse LLM output: %s\nRaw output:\n%s", exc, raw_content[:500])
        raise RuntimeError(
            f"LLM returned invalid output that could not be parsed into AutopsyExtraction: {exc}"
        ) from exc

    logger.info(
        "Extraction complete: cause_of_death=%r, confidence=%.2f, %d injuries, %d toxicology findings",
        extraction.cause_of_death,
        extraction.extraction_confidence,
        len(extraction.injury_patterns),
        len(extraction.toxicology_findings),
    )

    return extraction, model_name, elapsed


def _fallback_extract_findings(
    doc: PreprocessedDocument,
    model_used: str,
    elapsed: float,
) -> tuple[AutopsyExtraction, str, float]:
    """Conservative advisory extraction for offline/API-failure scenarios."""
    text = doc.raw_text or "\n".join(section.content for section in doc.sections)
    lower = text.lower()

    cause = _extract_cause_of_death(text)
    injuries = _extract_injuries(doc)
    observations = _extract_observations(text)
    contributing = _extract_contributing_factors(lower)

    extraction = AutopsyExtraction(
        case_identifier=_first_match(text, [r"\b(?:case|report)\s*(?:no\.?|number|id)?\s*[:#-]\s*([A-Z0-9/-]{4,})"]),
        date_of_exam=_first_match(text, [r"\bdate\s+of\s+(?:exam|examination)\s*[:#-]\s*([0-9]{1,4}[-/][0-9]{1,2}[-/][0-9]{1,4})"]),
        date_of_death=_first_match(text, [r"\bdate\s+of\s+death\s*[:#-]\s*([0-9]{1,4}[-/][0-9]{1,2}[-/][0-9]{1,4})"]),
        cause_of_death=cause,
        manner_of_death=_extract_manner(lower),
        certainty="possible" if cause else "undetermined",
        contributing_factors=contributing,
        injury_patterns=injuries,
        medical_observations=observations,
        postmortem_interval_estimate=_extract_postmortem_interval(text),
        extraction_confidence=0.45 if cause or injuries else 0.2,
        source_references={
            key: value
            for key, value in {
                "cause_of_death": _source_for_phrase(doc, cause) if cause else None,
                "manner_of_death": "rule-based text scan" if _extract_manner(lower) else None,
            }.items()
            if value
        },
    )
    extraction.validation_flags.append(
        "ADVISORY_RULE_BASED_FALLBACK: LLM extraction unavailable; review original source before use"
    )

    logger.info(
        "Fallback extraction complete: cause_of_death=%r, confidence=%.2f, %d injuries",
        extraction.cause_of_death,
        extraction.extraction_confidence,
        len(extraction.injury_patterns),
    )
    return extraction, model_used, elapsed


def _extract_cause_of_death(text: str) -> Optional[str]:
    explicit = _first_match(
        text,
        [
            r"(?:cause\s+of\s+death|causes?\s+of\s+death)\s*[:#-]\s*([^\n\r.;]{3,160})",
            r"(?:opinion|conclusion)\s*[:#-]\s*([^\n\r.;]*(?:death|haemorrhage|hemorrhage|trauma|asphyxia)[^\n\r.;]{0,120})",
        ],
    )
    if explicit:
        return explicit.strip(" -:")

    lower = text.lower()
    keyword_causes = [
        ("fatal haemorrhage", "Fatal haemorrhage"),
        ("fatal hemorrhage", "Fatal hemorrhage"),
        ("asphyxia", "Asphyxia"),
        ("gunshot", "Gunshot wound"),
        ("stab", "Stab wound"),
        ("blunt force", "Blunt force trauma"),
        ("trauma", "Traumatic injury"),
        ("drowning", "Drowning"),
        ("poison", "Poisoning"),
        ("myocardial infarction", "Myocardial infarction"),
    ]
    for needle, label in keyword_causes:
        if needle in lower:
            return label
    return None


def _extract_injuries(doc: PreprocessedDocument) -> list[InjuryObservation]:
    text = doc.raw_text or ""
    lower = text.lower()
    patterns = [
        ("stab", "torso", "stab wound"),
        ("laceration", "unspecified", "laceration"),
        ("fracture", "unspecified", "fracture"),
        ("contusion", "unspecified", "contusion"),
        ("abrasion", "unspecified", "abrasion"),
        ("gunshot", "unspecified", "gunshot wound"),
        ("burn", "unspecified", "burn"),
        ("defensive wound", "hands", "defensive wound"),
    ]

    injuries: list[InjuryObservation] = []
    seen: set[str] = set()
    for needle, region, injury_type in patterns:
        if needle not in lower:
            continue
        description = _sentence_containing(text, needle) or injury_type
        key = f"{injury_type}:{description.lower()}"
        if key in seen:
            continue
        seen.add(key)
        injuries.append(
            InjuryObservation(
                description=description[:240],
                body_region=_infer_body_region(description, region),
                injury_type=injury_type,
                severity="potentially significant",
                source_location=_source_for_phrase(doc, needle),
            )
        )
    return injuries[:12]


def _extract_manner(lower: str) -> Optional[MannerOfDeath]:
    for value in MannerOfDeath:
        if f"manner of death: {value.value}" in lower or f"manner: {value.value}" in lower:
            return value
    if any(word in lower for word in ["homicide", "murder"]):
        return MannerOfDeath.HOMICIDE
    if "suicide" in lower:
        return MannerOfDeath.SUICIDE
    if "accident" in lower:
        return MannerOfDeath.ACCIDENT
    if "natural" in lower:
        return MannerOfDeath.NATURAL
    return None


def _extract_contributing_factors(lower: str) -> list[str]:
    factors = []
    for keyword in ["internal bleeding", "peritonitis", "infection", "intoxication", "hypoxia"]:
        if keyword in lower:
            factors.append(keyword)
    return factors


def _extract_observations(text: str) -> list[str]:
    observations = []
    for keyword in ["weapon", "knife", "blood", "fingerprint", "footprint", "toxicology"]:
        sentence = _sentence_containing(text, keyword)
        if sentence and sentence not in observations:
            observations.append(sentence[:240])
    return observations[:8]


def _extract_postmortem_interval(text: str) -> Optional[str]:
    return _first_match(
        text,
        [
            r"(?:postmortem interval|time since death)\s*[:#-]\s*([^\n\r.;]{3,120})",
            r"\b([0-9]+(?:\s*-\s*[0-9]+)?\s*(?:hours|hrs|days)\s+(?:since|after)\s+death)\b",
        ],
    )


def _first_match(text: str, patterns: list[str]) -> Optional[str]:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return " ".join(match.group(1).split())
    return None


def _sentence_containing(text: str, keyword: str) -> Optional[str]:
    match = re.search(rf"[^.\n\r]{{0,160}}\b{re.escape(keyword)}\b[^.\n\r]{{0,160}}", text, flags=re.IGNORECASE)
    if not match:
        return None
    return " ".join(match.group(0).split())


def _infer_body_region(description: str, default: str) -> str:
    lower = description.lower()
    for region in ["head", "neck", "chest", "abdomen", "back", "arm", "hand", "leg", "lung", "liver"]:
        if region in lower:
            return region
    return default


def _source_for_phrase(doc: PreprocessedDocument, phrase: Optional[str]) -> str:
    if not phrase:
        return "rule-based text scan"
    phrase_lower = phrase.lower()
    for section in doc.sections:
        if phrase_lower in section.content.lower():
            return f"page {section.page_number}, section {section.name}"
    return "rule-based text scan"
