"""Schemas for deterministic Answer Quality Evaluation.

The evaluator is offline and does not call an LLM judge. Future judge fields are
kept out of CI gates and can be added as optional report metadata later.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class AnswerQualityStatus(StrEnum):
    """Case or gate status for answer quality evaluation."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class RequiredSectionCheck(BaseModel):
    """Presence check for one required Action Brief section."""

    section_title: str
    present: bool


class EvidenceCoverageCheck(BaseModel):
    """Coverage check for required evidence, gap, technology, or RAG identifiers."""

    coverage_type: str
    required_ids: list[str] = Field(default_factory=list)
    present_ids: list[str] = Field(default_factory=list)
    missing_ids: list[str] = Field(default_factory=list)
    coverage: float = 1.0


class UnsupportedClaim(BaseModel):
    """A deterministic unsupported claim match found in the answer text."""

    claim: str
    source: str
    reason: str


class AnswerQualityMetrics(BaseModel):
    """Deterministic metrics for a single answer quality eval case."""

    required_sections_present: bool
    missing_evidence_preserved: bool
    uncertainty_preserved: bool
    recommended_motion_consistent: bool
    required_evidence_ids_present: bool
    required_gap_ids_present: bool
    required_technology_ids_present: bool
    unsupported_claim_count: int
    unsupported_claim_rate: float = 0.0
    rag_context_citation_coverage: float
    startup_evidence_citation_coverage: float
    citation_precision: float = 0.0
    forbidden_absolute_language_count: int
    answer_quality_status: AnswerQualityStatus
    nvidia_technology_gap_consistent: bool = True


class AnswerQualityGateResult(BaseModel):
    """Result of a deterministic answer quality gate."""

    gate_name: str
    status: AnswerQualityStatus
    passed: bool
    details: str


class AnswerQualityEvalCase(BaseModel):
    """Golden case expectations for evaluating a final Action Brief."""

    case_id: str
    description: str
    pipeline_case_id: str
    use_rag: bool = False
    required_sections: list[str] = Field(default_factory=list)
    expected_recommended_motion: str | None = None
    allowed_recommended_motions: list[str] = Field(default_factory=list)
    expect_missing_evidence: bool = False
    required_missing_evidence_terms: list[str] = Field(default_factory=list)
    expect_uncertainty: bool = False
    low_confidence_requires_uncertainty: bool = False
    required_evidence_ids: list[str] = Field(default_factory=list)
    required_gap_ids: list[str] = Field(default_factory=list)
    required_technology_ids: list[str] = Field(default_factory=list)
    required_rag_source_ids: list[str] = Field(default_factory=list)
    unsupported_claim_patterns: list[str] = Field(default_factory=list)
    forbidden_absolute_language: list[str] = Field(
        default_factory=lambda: [
            "guaranteed",
            "always",
            "never",
            "proves",
            "will definitely",
            "100%",
        ]
    )
    max_unsupported_claim_count: int = 0
    max_forbidden_absolute_language_count: int = 0
    min_rag_context_citation_coverage: float = 0.0
    min_startup_evidence_citation_coverage: float = 1.0


class AnswerQualityEvalResult(BaseModel):
    """Evaluation result for one answer quality golden case."""

    case_id: str
    case_description: str
    passed: bool
    metrics: AnswerQualityMetrics
    gates: list[AnswerQualityGateResult] = Field(default_factory=list)
    required_section_checks: list[RequiredSectionCheck] = Field(default_factory=list)
    evidence_coverage_checks: list[EvidenceCoverageCheck] = Field(default_factory=list)
    unsupported_claims: list[UnsupportedClaim] = Field(default_factory=list)
    failure_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
