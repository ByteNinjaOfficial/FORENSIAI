"""Tests for aiventra.core.rule_preprocessor — section detection, PII redaction, normalization."""

import pytest

from aiventra.core.rule_preprocessor import (
    detect_sections,
    normalize_dates,
    normalize_measurements,
    preprocess,
    redact_pii,
)
from aiventra.core.schemas import PreprocessedDocument


class TestDetectSections:
    def test_single_section(self):
        text = "External Examination\nThe body is that of an adult male."
        sections = detect_sections(text)
        assert len(sections) == 1
        assert sections[0].name == "external examination"
        assert "adult male" in sections[0].content

    def test_multiple_sections(self):
        text = (
            "External Examination\nBody is intact.\n\n"
            "Internal Examination\nOrgans are normal.\n\n"
            "Toxicology\nNo substances detected."
        )
        sections = detect_sections(text)
        assert len(sections) == 3
        assert sections[0].name == "external examination"
        assert sections[1].name == "internal examination"
        assert sections[2].name == "toxicology"

    def test_page_headers(self):
        text = (
            "--- Page 1 ---\n"
            "External Examination\nBody is intact.\n"
            "--- Page 2 ---\n"
            "Toxicology\nNo substances detected."
        )
        sections = detect_sections(text)
        assert len(sections) == 2
        assert sections[0].page_number == 1
        assert sections[1].page_number == 2

    def test_numbered_section_headers(self):
        text = "1. Cause of Death\nBlunt force trauma.\n2. Manner of Death\nHomicide."
        sections = detect_sections(text)
        assert len(sections) == 2
        assert sections[0].name == "cause of death"
        assert sections[1].name == "manner of death"

    def test_no_sections(self):
        text = "This is just plain text with no section headers."
        sections = detect_sections(text)
        assert len(sections) == 0


class TestRedactPII:
    def test_redact_ssn(self):
        text = "SSN: 123-45-6789"
        redacted, fields = redact_pii(text)
        assert "123-45-6789" not in redacted
        assert "REDACTED_SOCIAL_SECURITY" in redacted
        assert "social_security" in fields

    def test_redact_email(self):
        text = "Contact: john.doe@example.com"
        redacted, fields = redact_pii(text)
        assert "john.doe@example.com" not in redacted
        assert "email" in fields

    def test_redact_phone(self):
        text = "Phone: (555) 123-4567"
        redacted, fields = redact_pii(text)
        assert "(555) 123-4567" not in redacted
        assert "phone" in fields

    def test_no_pii(self):
        text = "The body showed no signs of trauma."
        redacted, fields = redact_pii(text)
        assert redacted == text
        assert fields == []

    def test_multiple_pii_types(self):
        text = "SSN: 123-45-6789 Email: test@example.com Phone: 555-123-4567"
        redacted, fields = redact_pii(text)
        assert len(fields) >= 2
        assert "123-45-6789" not in redacted
        assert "test@example.com" not in redacted


class TestNormalizeMeasurements:
    def test_normalize_cm(self):
        assert "5 cm" == normalize_measurements("5cm")

    def test_normalize_kg(self):
        assert "72.5 kg" == normalize_measurements("72.5kg")

    def test_normalize_mg(self):
        assert "10 mg" == normalize_measurements("10mg")

    def test_already_normalized(self):
        assert "5 cm" == normalize_measurements("5 cm")

    def test_mixed(self):
        result = normalize_measurements("Liver: 1850g, Spleen: 150 g, Length: 170cm")
        assert "1850 g" in result
        assert "150 g" in result
        assert "170 cm" in result


class TestNormalizeDates:
    def test_mmddyyyy(self):
        assert "2024-03-15" == normalize_dates("03/15/2024")

    def test_mmddyyyy_no_leading_zero(self):
        assert "2024-03-05" == normalize_dates("3/5/2024")

    def test_dash_format(self):
        assert "2024-03-15" == normalize_dates("03-15-2024")

    def test_already_iso(self):
        assert "2024-03-15" == normalize_dates("2024-03-15")


class TestPreprocess:
    def test_full_pipeline(self):
        raw_text = "External Examination\nThe body weighs 70kg.\nSSN: 123-45-6789"
        result = preprocess(raw_text, [], 1, redact=True)
        assert isinstance(result, PreprocessedDocument)
        assert len(result.sections) == 1
        assert "70 kg" in result.raw_text
        assert "123-45-6789" not in result.raw_text
        assert "social_security" in result.redacted_fields

    def test_no_redact(self):
        raw_text = "SSN: 123-45-6789"
        result = preprocess(raw_text, [], 1, redact=False)
        assert "123-45-6789" in result.raw_text
        assert result.redacted_fields == []