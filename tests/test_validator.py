"""Tests for aiventra.core.validator — post-LLM extraction validation."""

import pytest

from aiventra.core.schemas import (
    AutopsyExtraction,
    Certainty,
    InjuryObservation,
    MannerOfDeath,
    PreprocessedDocument,
    SectionContent,
    ToxicologyFinding,
)
from aiventra.core.validator import (
    check_critical_fields,
    cross_reference_cause_of_death,
    cross_reference_injuries,
    cross_reference_manner_of_death,
    validate,
)


def _doc_with_text(text: str) -> PreprocessedDocument:
    return PreprocessedDocument(raw_text=text, page_count=1)


class TestCheckCriticalFields:
    def test_all_missing(self):
        ext = AutopsyExtraction()
        flags = check_critical_fields(ext)
        assert any("cause_of_death" in f for f in flags)
        assert any("manner_of_death" in f for f in flags)

    def test_all_present(self):
        ext = AutopsyExtraction(
            cause_of_death="Blunt force trauma",
            manner_of_death=MannerOfDeath.ACCIDENT,
            date_of_death="2024-01-01",
            date_of_exam="2024-01-02",
        )
        flags = check_critical_fields(ext)
        assert len(flags) == 0

    def test_partial_missing(self):
        ext = AutopsyExtraction(
            cause_of_death="Myocardial infarction",
        )
        flags = check_critical_fields(ext)
        assert any("manner_of_death" in f for f in flags)
        assert any("date_of_death" in f for f in flags)
        assert not any("cause_of_death" in f for f in flags)


class TestCrossReferenceCauseOfDeath:
    def test_cause_found_in_text(self):
        ext = AutopsyExtraction(cause_of_death="blunt force trauma")
        doc = _doc_with_text("The cause of death is blunt force trauma to the head.")
        flags, refs = cross_reference_cause_of_death(ext, doc.raw_text)
        assert len(flags) == 0
        assert "cause_of_death" in refs

    def test_cause_not_found_but_keywords_exist(self):
        ext = AutopsyExtraction(cause_of_death="spontaneous combustion")
        doc = _doc_with_text("The cause of death is blunt force trauma.")
        flags, refs = cross_reference_cause_of_death(ext, doc.raw_text)
        assert any("HALLUCINATION_SUSPECT" in f for f in flags)

    def test_no_cause_extracted(self):
        ext = AutopsyExtraction()
        doc = _doc_with_text("Some text")
        flags, refs = cross_reference_cause_of_death(ext, doc.raw_text)
        assert len(flags) == 0


class TestCrossReferenceMannerOfDeath:
    def test_manner_found_in_text(self):
        ext = AutopsyExtraction(manner_of_death=MannerOfDeath.HOMICIDE)
        doc = _doc_with_text("The manner of death is homicide.")
        flags, refs = cross_reference_manner_of_death(ext, doc.raw_text)
        assert len(flags) == 0
        assert "manner_of_death" in refs

    def test_manner_not_found(self):
        ext = AutopsyExtraction(manner_of_death=MannerOfDeath.SUICIDE)
        doc = _doc_with_text("The manner of death is natural.")
        flags, refs = cross_reference_manner_of_death(ext, doc.raw_text)
        assert any("HALLUCINATION_SUSPECT" in f for f in flags)

    def test_natural_manner(self):
        ext = AutopsyExtraction(manner_of_death=MannerOfDeath.NATURAL)
        doc = _doc_with_text("Death due to natural causes.")
        flags, refs = cross_reference_manner_of_death(ext, doc.raw_text)
        assert len(flags) == 0


class TestCrossReferenceInjuries:
    def test_injury_found(self):
        ext = AutopsyExtraction(
            injury_patterns=[
                InjuryObservation(
                    description="skull fracture on the left parietal bone",
                    body_region="head",
                    injury_type="fracture",
                    source_location="page 3",
                )
            ]
        )
        doc = _doc_with_text("There is a skull fracture on the left parietal bone.")
        flags, refs = cross_reference_injuries(ext, doc.raw_text)
        assert len(flags) == 0
        assert len(refs) == 1

    def test_injury_not_found(self):
        ext = AutopsyExtraction(
            injury_patterns=[
                InjuryObservation(
                    description="gunshot wound to the chest",
                    body_region="chest",
                    injury_type="gunshot",
                    source_location="page 3",
                )
            ]
        )
        doc = _doc_with_text("No injuries were observed on external examination.")
        flags, refs = cross_reference_injuries(ext, doc.raw_text)
        assert any("HALLUCINATION_SUSPECT" in f for f in flags)


class TestValidateIntegration:
    def test_valid_extraction(self):
        ext = AutopsyExtraction(
            cause_of_death="blunt force trauma",
            manner_of_death=MannerOfDeath.ACCIDENT,
            certainty=Certainty.CONFIRMED,
            date_of_death="2024-01-01",
            date_of_exam="2024-01-02",
            extraction_confidence=0.9,
        )
        doc = _doc_with_text(
            "Cause of death is blunt force trauma. "
            "The manner of death is accident."
        )
        result = validate(ext, doc)
        assert result.is_valid is True
        assert len(result.flags) == 0

    def test_flagged_extraction(self):
        ext = AutopsyExtraction(
            cause_of_death="spontaneous combustion",
            manner_of_death=MannerOfDeath.SUICIDE,
            extraction_confidence=0.8,
            injury_patterns=[
                InjuryObservation(
                    description="catastrophic thermal decomposition",
                    body_region="full body",
                    injury_type="thermal",
                    source_location="page 1",
                )
            ],
        )
        doc = _doc_with_text(
            "Cause of death is blunt force trauma. "
            "Manner of death is homicide."
        )
        result = validate(ext, doc)
        assert result.is_valid is False
        assert any("HALLUCINATION_SUSPECT" in f for f in result.flags)