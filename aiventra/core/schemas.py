"""Pydantic schemas for autopsy report extraction.

These models define the structured output contract used across all pipeline stages.
Every field in AutopsyExtraction links back to its source location for auditability.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Certainty(str, Enum):
    CONFIRMED = "confirmed"
    PROBABLE = "probable"
    POSSIBLE = "possible"
    UNDETERMINED = "undetermined"


class MannerOfDeath(str, Enum):
    NATURAL = "natural"
    ACCIDENT = "accident"
    HOMICIDE = "homicide"
    SUICIDE = "suicide"
    UNDETERMINED = "undetermined"
    PENDING = "pending"


class InjuryObservation(BaseModel):
    description: str
    body_region: str
    injury_type: str
    severity: Optional[str] = None
    source_location: str = Field(
        description="Page and paragraph in original document for audit trail"
    )


class ToxicologyFinding(BaseModel):
    substance: str
    concentration: Optional[str] = None
    unit: Optional[str] = None
    significance: Optional[str] = None
    source_location: str = Field(
        description="Page and paragraph in original document for audit trail"
    )


class AutopsyExtraction(BaseModel):
    case_identifier: Optional[str] = None
    date_of_exam: Optional[str] = None
    date_of_death: Optional[str] = None
    cause_of_death: Optional[str] = None
    manner_of_death: Optional[MannerOfDeath] = None
    certainty: Certainty = Certainty.UNDETERMINED
    contributing_factors: List[str] = Field(default_factory=list)
    injury_patterns: List[InjuryObservation] = Field(default_factory=list)
    medical_observations: List[str] = Field(default_factory=list)
    toxicology_findings: List[ToxicologyFinding] = Field(default_factory=list)
    postmortem_interval_estimate: Optional[str] = None
    extraction_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall confidence in extraction accuracy (0.0-1.0)",
    )
    validation_flags: List[str] = Field(
        default_factory=list,
        description="Anomalies, hallucination suspects, missing critical fields",
    )
    source_references: dict = Field(
        default_factory=dict,
        description="Maps extracted field name to source location (page/paragraph)",
    )


class SectionContent(BaseModel):
    name: str
    content: str
    page_number: int
    start_paragraph: Optional[int] = None


class PreprocessedDocument(BaseModel):
    raw_text: str
    sections: List[SectionContent] = Field(default_factory=list)
    page_count: int
    tables: List[dict] = Field(
        default_factory=list,
        description="Extracted table data as list of dicts",
    )
    redacted_fields: List[str] = Field(
        default_factory=list,
        description="PII fields that were redacted before LLM call",
    )
    document_type: Optional[str] = Field(
        default=None,
        description="Detected document type: autopsy, crime_scene, or unknown",
    )


class ValidationResult(BaseModel):
    is_valid: bool = True
    confidence_adjustment: float = 0.0
    flags: List[str] = Field(default_factory=list)
    cross_references: dict = Field(
        default_factory=dict,
        description="Maps extracted field to raw text snippet for verification",
    )


class ExtractionResult(BaseModel):
    extraction: AutopsyExtraction
    validation: ValidationResult
    preprocessed: PreprocessedDocument
    model_used: Optional[str] = None
    processing_time_seconds: Optional[float] = None