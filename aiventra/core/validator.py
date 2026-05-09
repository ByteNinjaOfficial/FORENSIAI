"""Post-LLM validation for extracted autopsy findings.

Cross-references LLM output against the raw document text to detect
hallucinations, missing critical fields, and inconsistencies. Produces
a ValidationResult with flags and confidence adjustments.
"""

from __future__ import annotations

import logging
import re
from typing import List

from aiventra.core.schemas import AutopsyExtraction, MannerOfDeath, PreprocessedDocument, ValidationResult

logger = logging.getLogger(__name__)

CRITICAL_FIELDS = [
    "cause_of_death",
    "manner_of_death",
    "date_of_death",
]

CAUSE_OF_DEATH_KEYWORDS = [
    "cause of death",
    "apparent cause of death",
    "due to",
    "caused by",
    "resulted from",
    "attributed to",
    "died from",
    "manner of death",
    "apparent manner of death",
]

MANNER_KEYWORDS: dict[str, List[str]] = {
    MannerOfDeath.NATURAL: ["natural", "natural causes", "disease"],
    MannerOfDeath.ACCIDENT: ["accident", "accidental", "unintentional"],
    MannerOfDeath.HOMICIDE: ["homicide", "homicidal", "killed by", "murder"],
    MannerOfDeath.SUICIDE: ["suicide", "suicidal", "self-inflicted", "took own life"],
    MannerOfDeath.UNDETERMINED: ["undetermined", "could not be determined", "inconclusive"],
}


def _text_contains_any(text: str, keywords: List[str]) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in keywords)


def _find_source_snippet(text: str, phrase: str, window: int = 100) -> str:
    idx = text.lower().find(phrase.lower())
    if idx == -1:
        return ""
    start = max(0, idx - window)
    end = min(len(text), idx + len(phrase) + window)
    return text[start:end].strip()


def check_critical_fields(extraction: AutopsyExtraction) -> List[str]:
    """Flag missing critical fields."""
    flags: List[str] = []
    if not extraction.cause_of_death:
        flags.append("MISSING_CRITICAL: cause_of_death is empty")
    if extraction.manner_of_death is None:
        flags.append("MISSING_CRITICAL: manner_of_death is empty")
    if not extraction.date_of_death:
        flags.append("MISSING: date_of_death is empty")
    if not extraction.date_of_exam:
        flags.append("MISSING: date_of_exam is empty")
    return flags


def cross_reference_cause_of_death(
    extraction: AutopsyExtraction, raw_text: str
) -> tuple[List[str], dict]:
    """Verify cause of death against raw text using keyword overlap."""
    flags: List[str] = []
    refs: dict = {}

    if not extraction.cause_of_death:
        return flags, refs

    snippet = _find_source_snippet(raw_text, extraction.cause_of_death)
    if snippet:
        refs["cause_of_death"] = snippet
    else:
        cause_words = [w for w in re.findall(r"\w+", extraction.cause_of_death.lower()) if len(w) > 3]
        lower_text = raw_text.lower()
        overlap = sum(1 for w in cause_words if w in lower_text)
        overlap_ratio = overlap / len(cause_words) if cause_words else 0

        if overlap_ratio >= 0.4:
            best_word = max(cause_words, key=lambda w: lower_text.find(w) if w in lower_text else len(lower_text))
            snippet = _find_source_snippet(raw_text, best_word)
            if snippet:
                refs["cause_of_death"] = snippet
        elif overlap_ratio >= 0.2:
            best_word = max(cause_words, key=lambda w: lower_text.find(w) if w in lower_text else len(lower_text))
            snippet = _find_source_snippet(raw_text, best_word)
            if snippet:
                refs["cause_of_death"] = snippet
            flags.append(
                "POSSIBLE_PARAPHRASE: cause_of_death partially matches source text "
                f"(overlap {overlap_ratio:.0%}), may be LLM paraphrase"
            )
        elif _text_contains_any(raw_text, CAUSE_OF_DEATH_KEYWORDS):
            flags.append(
                "HALLUCINATION_SUSPECT: cause_of_death not found verbatim in source, "
                "though cause-of-death section exists in document"
            )
        else:
            flags.append(
                "LOW_CONFIDENCE: cause_of_death not found verbatim, "
                "and no cause-of-death keywords found in document"
            )

    return flags, refs


def cross_reference_manner_of_death(
    extraction: AutopsyExtraction, raw_text: str
) -> tuple[List[str], dict]:
    """Verify manner of death keywords appear in raw text."""
    flags: List[str] = []
    refs: dict = {}

    if extraction.manner_of_death is None:
        return flags, refs

    expected_keywords = MANNER_KEYWORDS.get(extraction.manner_of_death, [])
    found = _text_contains_any(raw_text, expected_keywords)

    if found:
        for kw in expected_keywords:
            snippet = _find_source_snippet(raw_text, kw)
            if snippet:
                refs["manner_of_death"] = snippet
                break
    else:
        flags.append(
            f"HALLUCINATION_SUSPECT: manner_of_death={extraction.manner_of_death.value} "
            f"but no supporting keywords ({', '.join(expected_keywords)}) found in document"
        )

    return flags, refs


def cross_reference_injuries(
    extraction: AutopsyExtraction, raw_text: str
) -> tuple[List[str], dict]:
    """Spot-check injury descriptions against raw text."""
    flags: List[str] = []
    refs: dict = {}
    lower_text = raw_text.lower()

    for i, injury in enumerate(extraction.injury_patterns):
        key_words = [w for w in re.findall(r"\w+", injury.description.lower()) if len(w) > 4]
        matched = any(w in lower_text for w in key_words)
        if matched:
            for kw in key_words:
                snippet = _find_source_snippet(raw_text, kw)
                if snippet:
                    refs[f"injury_{i}_{injury.body_region}"] = snippet
                    break
        else:
            flags.append(
                f"HALLUCINATION_SUSPECT: injury #{i + 1} "
                f"('{injury.description[:50]}...') not corroborated in source text"
            )

    return flags, refs


def validate_confidence(extraction: AutopsyExtraction, flags: List[str]) -> float:
    """Adjust extraction confidence based on validation flags."""
    adjustment = 0.0
    for flag in flags:
        if flag.startswith("MISSING_CRITICAL"):
            adjustment -= 0.15
        elif flag.startswith("HALLUCINATION_SUSPECT"):
            adjustment -= 0.10
        elif flag.startswith("LOW_CONFIDENCE"):
            adjustment -= 0.10
        elif flag.startswith("POSSIBLE_PARAPHRASE"):
            adjustment -= 0.05
        elif flag.startswith("MISSING"):
            adjustment -= 0.05

    new_confidence = max(0.0, min(1.0, extraction.extraction_confidence + adjustment))
    return round(new_confidence, 2)


def validate(
    extraction: AutopsyExtraction,
    doc: PreprocessedDocument,
) -> ValidationResult:
    """Run full validation pipeline on an extraction against its source document.

    Args:
        extraction: The LLM-extracted findings.
        doc: The preprocessed source document.

    Returns:
        ValidationResult with flags, cross-references, and confidence adjustment.
    """
    raw_text = doc.raw_text
    all_flags: List[str] = []
    all_refs: dict = {}

    all_flags.extend(check_critical_fields(extraction))

    cod_flags, cod_refs = cross_reference_cause_of_death(extraction, raw_text)
    all_flags.extend(cod_flags)
    all_refs.update(cod_refs)

    mod_flags, mod_refs = cross_reference_manner_of_death(extraction, raw_text)
    all_flags.extend(mod_flags)
    all_refs.update(mod_refs)

    inj_flags, inj_refs = cross_reference_injuries(extraction, raw_text)
    all_flags.extend(inj_flags)
    all_refs.update(inj_refs)

    confidence_adjustment = validate_confidence(extraction, all_flags) - extraction.extraction_confidence

    is_valid = not any(f.startswith(("MISSING_CRITICAL", "LOW_CONFIDENCE", "HALLUCINATION_SUSPECT")) for f in all_flags)

    if all_flags:
        logger.warning("Validation flags: %s", all_flags)
    else:
        logger.info("Validation passed with no flags")

    return ValidationResult(
        is_valid=is_valid,
        confidence_adjustment=confidence_adjustment,
        flags=all_flags,
        cross_references=all_refs,
    )