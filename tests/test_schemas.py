"""Tests for aiventra.core.schemas — Pydantic model validation."""

import pytest
from pydantic import ValidationError

from aiventra.core.schemas import (
    AutopsyExtraction,
    Certainty,
    ExtractionResult,
    InjuryObservation,
    MannerOfDeath,
    PreprocessedDocument,
    SectionContent,
    ToxicologyFinding,
    ValidationResult,
)


class TestAutopsyExtraction:
    def test_minimal_valid(self):
        ext = AutopsyExtraction()
        assert ext.cause_of_death is None
        assert ext.manner_of_death is None
        assert ext.certainty == Certainty.UNDETERMINED
        assert ext.injury_patterns == []
        assert ext.toxicology_findings == []
        assert ext.extraction_confidence == 0.0

    def test_full_extraction(self):
        ext = AutopsyExtraction(
            case_identifier="ME-2024-0142",
            date_of_exam="2024-03-15",
            date_of_death="2024-03-14",
            cause_of_death="Blunt force trauma to the head",
            manner_of_death=MannerOfDeath.HOMICIDE,
            certainty=Certainty.CONFIRMED,
            contributing_factors=["skull fracture", "subdural hematoma"],
            injury_patterns=[
                InjuryObservation(
                    description="Linear skull fracture, left parietal bone",
                    body_region="head",
                    injury_type="fracture",
                    severity="severe",
                    source_location="page 3, External Examination",
                )
            ],
            toxicology_findings=[
                ToxicologyFinding(
                    substance="Ethanol",
                    concentration="0.08",
                    unit="g/dL",
                    significance="elevated",
                    source_location="page 5, Toxicology",
                )
            ],
            extraction_confidence=0.92,
        )
        assert ext.cause_of_death == "Blunt force trauma to the head"
        assert ext.manner_of_death == MannerOfDeath.HOMICIDE
        assert len(ext.injury_patterns) == 1
        assert ext.injury_patterns[0].body_region == "head"
        assert len(ext.toxicology_findings) == 1

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            AutopsyExtraction(extraction_confidence=1.5)
        with pytest.raises(ValidationError):
            AutopsyExtraction(extraction_confidence=-0.1)

    def test_serialization_roundtrip(self):
        ext = AutopsyExtraction(
            cause_of_death="Myocardial infarction",
            manner_of_death=MannerOfDeath.NATURAL,
            extraction_confidence=0.85,
        )
        json_str = ext.model_dump_json()
        restored = AutopsyExtraction.model_validate_json(json_str)
        assert restored.cause_of_death == ext.cause_of_death
        assert restored.manner_of_death == ext.manner_of_death


class TestSectionContent:
    def test_valid_section(self):
        sec = SectionContent(
            name="external examination",
            content="The body is that of an adult male...",
            page_number=2,
        )
        assert sec.name == "external examination"
        assert sec.page_number == 2

    def test_with_paragraph(self):
        sec = SectionContent(
            name="toxicology",
            content="Ethanol: 0.08 g/dL",
            page_number=5,
            start_paragraph=3,
        )
        assert sec.start_paragraph == 3


class TestPreprocessedDocument:
    def test_minimal(self):
        doc = PreprocessedDocument(
            raw_text="some text",
            page_count=1,
        )
        assert doc.raw_text == "some text"
        assert doc.sections == []
        assert doc.redacted_fields == []

    def test_with_sections_and_tables(self):
        doc = PreprocessedDocument(
            raw_text="full text",
            sections=[
                SectionContent(name="summary", content="test", page_number=1),
            ],
            page_count=3,
            tables=[{"substance": "Ethanol", "concentration": "0.08"}],
            redacted_fields=["social_security"],
        )
        assert len(doc.sections) == 1
        assert len(doc.tables) == 1


class TestValidationResult:
    def test_valid_default(self):
        result = ValidationResult()
        assert result.is_valid is True
        assert result.flags == []

    def test_with_flags(self):
        result = ValidationResult(
            is_valid=False,
            confidence_adjustment=-0.15,
            flags=["HALLUCINATION_SUSPECT: cause_of_death not found"],
        )
        assert result.is_valid is False
        assert len(result.flags) == 1


class TestExtractionResult:
    def test_full_result(self):
        result = ExtractionResult(
            extraction=AutopsyExtraction(),
            validation=ValidationResult(),
            preprocessed=PreprocessedDocument(raw_text="test", page_count=1),
            model_used="deepseek-ai/DeepSeek-V4-Pro",
            processing_time_seconds=3.14,
        )
        assert result.model_used == "deepseek-ai/DeepSeek-V4-Pro"
        json_out = result.model_dump_json()
        assert "deepseek" in json_out