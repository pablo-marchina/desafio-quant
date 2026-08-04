"""Schemas for gap diagnosis and NVIDIA technology mapping."""

from __future__ import annotations

from enum import Enum, StrEnum
from typing import Any

from pydantic import BaseModel, Field

from src.extraction.schemas import ConfidenceLevel, TechnicalGap
from src.validation.evidence_validator import ValidatedEvidence


class EvidenceTag(StrEnum):
    FACT = "fact"
    INFERRED = "inferred"
    HYPOTHESIS = "hypothesis"


class GapWithEvidence(BaseModel):
    gap: TechnicalGap
    detected: bool
    confidence: ConfidenceLevel
    evidence_tag: EvidenceTag
    reasoning: str
    evidence_used: list[ValidatedEvidence] = Field(default_factory=list)


class NvidiaTechnologyCandidate(BaseModel):
    technology_name: str
    addresses_gap: TechnicalGap
    justification: str


class GapDiagnosisResult(BaseModel):
    startup_name: str
    diagnosed_gaps: list[GapWithEvidence]
    nvidia_technology_candidates: list[NvidiaTechnologyCandidate] = Field(default_factory=list)
    confidence: ConfidenceLevel
    reasoning: str
    evidence_used: list[ValidatedEvidence] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)


# ── Quantitative Gap Diagnosis Models ──────────────────────────────────────


class GapType(str, Enum):
    COMPUTE_ACCELERATION_GAP = "compute_acceleration_gap"
    INFERENCE_PERFORMANCE_GAP = "inference_performance_gap"
    TRAINING_SCALABILITY_GAP = "training_scalability_gap"
    MLOPS_DEPLOYMENT_GAP = "mlops_deployment_gap"
    DATA_PIPELINE_GAP = "data_pipeline_gap"
    MODEL_OPTIMIZATION_GAP = "model_optimization_gap"
    COMPUTER_VISION_GAP = "computer_vision_gap"
    GENAI_LLM_GAP = "genai_llm_gap"
    CYBERSECURITY_AI_GAP = "cybersecurity_ai_gap"
    NVIDIA_ECOSYSTEM_FIT_GAP = "nvidia_ecosystem_fit_gap"
    EVIDENCE_COVERAGE_GAP = "evidence_coverage_gap"
    TECHNICAL_DEPTH_GAP = "technical_depth_gap"


GAP_TECH_MAP: dict[GapType, list[TechnicalGap]] = {
    GapType.COMPUTE_ACCELERATION_GAP: [
        TechnicalGap.HIGH_INFERENCE_COST,
        TechnicalGap.HIGH_LATENCY,
    ],
    GapType.INFERENCE_PERFORMANCE_GAP: [
        TechnicalGap.HIGH_INFERENCE_COST,
        TechnicalGap.HIGH_LATENCY,
    ],
    GapType.TRAINING_SCALABILITY_GAP: [
        TechnicalGap.HIGH_INFERENCE_COST,
        TechnicalGap.MODEL_EVALUATION_GAP,
    ],
    GapType.MLOPS_DEPLOYMENT_GAP: [
        TechnicalGap.OBSERVABILITY_GAP,
        TechnicalGap.MODEL_EVALUATION_GAP,
        TechnicalGap.AGENT_GOVERNANCE_GAP,
    ],
    GapType.DATA_PIPELINE_GAP: [TechnicalGap.SLOW_DATA_PIPELINE],
    GapType.MODEL_OPTIMIZATION_GAP: [
        TechnicalGap.MODEL_EVALUATION_GAP,
        TechnicalGap.HIGH_INFERENCE_COST,
    ],
    GapType.COMPUTER_VISION_GAP: [TechnicalGap.COMPUTER_VISION_NEED],
    GapType.GENAI_LLM_GAP: [TechnicalGap.EXTERNAL_API_DEPENDENCY],
    GapType.CYBERSECURITY_AI_GAP: [TechnicalGap.AI_CYBERSECURITY_NEED],
    GapType.NVIDIA_ECOSYSTEM_FIT_GAP: [
        TechnicalGap.HIGH_INFERENCE_COST,
        TechnicalGap.SLOW_DATA_PIPELINE,
        TechnicalGap.COMPUTER_VISION_NEED,
    ],
    GapType.EVIDENCE_COVERAGE_GAP: [],
    GapType.TECHNICAL_DEPTH_GAP: [],
}

ALL_GAP_TYPES: list[GapType] = list(GapType)


class GapSeverityFeatures(BaseModel):
    missing_required_signal_count: float = Field(ge=0.0, le=1.0)
    weak_evidence_count: float = Field(ge=0.0, le=1.0)
    rejected_evidence_count: float = Field(ge=0.0, le=1.0)
    unsupported_claim_count: float = Field(ge=0.0, le=1.0)
    low_confidence_evidence_count: float = Field(ge=0.0, le=1.0)
    relevant_signal_absence: float = Field(ge=0.0, le=1.0)
    nvidia_fit_opportunity_signal_count: float = Field(ge=0.0, le=1.0)
    implementation_complexity_proxy: float = Field(ge=0.0, le=1.0)
    business_impact_proxy: float = Field(ge=0.0, le=1.0)
    uncertainty_penalty: float = Field(ge=0.0, le=1.0)


class GapConfidenceFeatures(BaseModel):
    supporting_evidence_count: float = Field(ge=0.0, le=1.0)
    supporting_source_count: float = Field(ge=0.0, le=1.0)
    average_evidence_confidence: float = Field(ge=0.0, le=1.0)
    average_source_quality: float = Field(ge=0.0, le=1.0)
    cross_source_agreement_count: float = Field(ge=0.0, le=1.0)
    contradiction_count: float = Field(ge=0.0, le=1.0)
    extraction_success_rate: float = Field(ge=0.0, le=1.0)
    source_category_coverage: float = Field(ge=0.0, le=1.0)


class GapDiagnosisFeatures(BaseModel):
    severity: GapSeverityFeatures
    confidence: GapConfidenceFeatures


class GapDiagnosisStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"
    BLOCKED_UNCALIBRATED_GAP_DIAGNOSIS = "blocked_uncalibrated_gap_diagnosis"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"


class GapDiagnosisResultItem(BaseModel):
    gap_id: str
    gap_type: GapType
    severity_score: float = Field(ge=0.0, le=1.0)
    confidence_score: float = Field(ge=0.0, le=1.0)
    uncertainty: float = Field(ge=0.0, le=1.0)
    status: GapDiagnosisStatus
    features: GapDiagnosisFeatures
    weights: dict[str, Any]
    thresholds: dict[str, float]
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    related_claim_ids: list[str] = Field(default_factory=list)
    calibration_decision_ids: list[str] = Field(default_factory=list)
    production_allowed: bool = False
    blockers: list[str] = Field(default_factory=list)
    explanation: str = ""
    recommended_investigation: str = ""


class GapDiagnosisMetrics(BaseModel):
    total_gap_count: int = Field(ge=0)
    production_allowed_gap_count: int = Field(ge=0)
    blocked_gap_count: int = Field(ge=0)
    average_gap_severity: float = Field(ge=0.0, le=1.0)
    average_gap_confidence: float = Field(ge=0.0, le=1.0)
    high_severity_gap_count: int = Field(ge=0)
    evidence_coverage_gap_count: int = Field(ge=0)
    missing_calibration_count: int = Field(ge=0)
    calibrated_decision_count: int = Field(ge=0)
    gap_uncertainty_mean: float = Field(ge=0.0, le=1.0)


class GapDiagnosisSummary(BaseModel):
    run_id: str
    gap_diagnosis_status: GapDiagnosisStatus
    gaps: list[GapDiagnosisResultItem] = Field(default_factory=list)
    metrics: GapDiagnosisMetrics | None = None
    calibration_status: str = "uncalibrated"
    production_allowed: bool = False
    blockers: list[str] = Field(default_factory=list)
