from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from src.extraction.schemas import ConfidenceLevel
from src.rag.schemas import DroppedContext, PackedContext, SupportingNvidiaContext


class BriefVerdict(StrEnum):
    HIGH_PRIORITY = "high_priority"
    PROMISING = "promising"
    EARLY_STAGE = "early_stage"
    NEEDS_VALIDATION = "needs_validation"
    NOT_RECOMMENDED = "not_recommended"


class ActionBriefStatus(StrEnum):
    PASSED = "passed"
    NEEDS_REVIEW = "needs_review"
    BLOCKED_NO_PRODUCTION_RECOMMENDATIONS = "blocked_no_production_recommendations"
    BLOCKED_RANKING_NOT_PASSED = "blocked_ranking_not_passed"
    BLOCKED_QUALITY_GATE = "blocked_quality_gate"
    BLOCKED_UNCALIBRATED_INPUTS = "blocked_uncalibrated_inputs"
    FAILED_UNSUPPORTED_CRITICAL_CLAIM = "failed_unsupported_critical_claim"
    FAILED = "failed"
    FAILED_INCONSISTENCY = "failed_inconsistency"


class BriefUncertainty(BaseModel):
    description: str
    source: str
    impact: str


class BriefEvidenceItem(BaseModel):
    claim: str
    tag: str
    confidence: str
    source_url: str
    source_type: str


class BriefSection(BaseModel):
    title: str
    content: str
    items: list[BriefEvidenceItem] = Field(default_factory=list)


class TopRecommendation(BaseModel):
    recommendation_id: str
    nvidia_technology: str
    gap_id: str
    gap_type: str
    recommendation_priority_score: float = 0.0
    recommendation_confidence: float = 0.0
    uncertainty: float = 1.0
    mapping_score: float = 0.0
    mapping_confidence: float = 0.0
    business_impact: float = 0.0
    implementation_complexity: float = 0.0
    ai_native_score_value: float | None = None
    nvidia_fit_score_value: float | None = None
    gap_severity_score: float = 0.0
    gap_confidence_score: float = 0.0
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    supporting_rag_context_ids: list[str] = Field(default_factory=list)
    supporting_claim_ids: list[str] = Field(default_factory=list)
    calibration_decision_ids: list[str] = Field(default_factory=list)
    next_best_action: str = ""
    reason_grounded_in_scores: str = ""
    production_allowed: bool = False


class ActionBriefMetrics(BaseModel):
    recommendation_count: int = 0
    production_allowed_recommendation_count: int = 0
    blocked_recommendation_count: int = 0
    average_recommendation_priority_score: float = 0.0
    average_recommendation_confidence: float = 0.0
    recommendation_uncertainty_mean: float = 0.0
    covered_gap_count: int = 0
    total_gap_count: int = 0
    accepted_evidence_count: int = 0
    supporting_rag_context_count: int = 0
    rag_supported_recommendation_rate: float = 0.0
    evidence_supported_recommendation_rate: float = 0.0
    unsupported_critical_claims_count: int = 0
    blocker_count: int = 0
    calibration_decision_count: int = 0
    missing_calibration_count: int = 0


class Blockers(BaseModel):
    blocker_id: str = ""
    description: str
    source: str = ""
    severity: str = "high"


class AuditTrail(BaseModel):
    executed_nodes: list[str] = Field(default_factory=list)
    calibration_decision_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    rag_context_ids: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    quality_gate_status: str | None = None


class CalibrationSnapshot(BaseModel):
    total_decisions: int = 0
    calibrated_count: int = 0
    uncalibrated_count: int = 0
    blocked_count: int = 0
    production_allowed_count: int = 0
    calibration_coverage_ratio: float = 0.0
    calibration_decision_count: int = 0
    missing_calibration_count: int = 0


class QualityGateSnapshot(BaseModel):
    status: str = ""
    failed_checks: list[str] = Field(default_factory=list)
    warning_checks: list[str] = Field(default_factory=list)


class ActionBrief(BaseModel):
    run_id: str
    startup_id: str | None = None
    generated_at: str = ""
    brief_status: ActionBriefStatus = ActionBriefStatus.BLOCKED_NO_PRODUCTION_RECOMMENDATIONS
    executive_summary_quantitative: dict[str, Any] = Field(default_factory=dict)
    recommendation_summary: str = ""
    top_recommendations: list[TopRecommendation] = Field(default_factory=list)
    evidence_summary: str = ""
    rag_summary: str = ""
    gap_summary: str = ""
    scoring_summary: str = ""
    risk_summary: str = ""
    blockers: list[Blockers] = Field(default_factory=list)
    next_best_actions: list[str] = Field(default_factory=list)
    audit_trail: AuditTrail = Field(default_factory=AuditTrail)
    quality_gate_snapshot: QualityGateSnapshot = Field(default_factory=QualityGateSnapshot)
    calibration_snapshot: CalibrationSnapshot = Field(default_factory=CalibrationSnapshot)
    review_required: bool = False


class StartupActionBrief(BaseModel):
    startup_name: str
    website: str
    sector: str
    one_line_summary: str
    verdict: BriefVerdict
    final_priority_score: float
    recommended_motion: str
    confidence: ConfidenceLevel
    sections: list[BriefSection]
    ai_native_classification: dict
    defensibility_score: dict
    inception_fit_score: dict
    production_readiness_score: dict
    composite_score: dict
    diagnosed_gaps: list[dict]
    nvidia_technology_candidates: list[dict]
    recommendations: list[dict]
    evidence_used: list[BriefEvidenceItem]
    missing_evidence: list[str]
    uncertainties: list[BriefUncertainty]
    next_action_for_nvidia_team: str
    reasoning: str
    packed_rag_contexts: list[PackedContext] = Field(default_factory=list)
    supporting_nvidia_context: list[SupportingNvidiaContext] = Field(default_factory=list)
    dropped_contexts_debug: list[DroppedContext] = Field(default_factory=list)
