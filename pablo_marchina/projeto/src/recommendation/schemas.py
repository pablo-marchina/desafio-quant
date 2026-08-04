from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from src.extraction.schemas import (
    ConfidenceLevel,
    ImplementationComplexity,
    RecommendationPriority,
    TechnicalGap,
)
from src.validation.evidence_validator import ValidatedEvidence


class SuggestedTechnicalExperiment(BaseModel):
    title: str
    target_gap: TechnicalGap
    hypothesis: str
    success_metric: str
    estimated_duration: str
    nvidia_technology: str
    next_step: str


class RecommendedNextAction(StrEnum):
    APPROACH_NOW = "approach_now"
    VALIDATE_MANUALLY = "validate_manually"
    MONITOR = "monitor"
    NOT_RECOMMENDED = "not_recommended"


class PerGapRecommendation(BaseModel):
    diagnosed_gap: TechnicalGap
    detected: bool
    recommended_nvidia_technologies: list[str] = Field(default_factory=list)
    technical_justification: str = ""
    business_justification: str = ""
    priority: RecommendationPriority = RecommendationPriority.LOW
    implementation_complexity: ImplementationComplexity = ImplementationComplexity.MEDIUM
    suggested_experiment: SuggestedTechnicalExperiment | None = None
    action: RecommendedNextAction = RecommendedNextAction.NOT_RECOMMENDED
    next_action_for_nvidia_team: str = ""
    evidence_used: list[ValidatedEvidence] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.LOW


class RecommendationResult(BaseModel):
    startup_name: str
    overall_priority: RecommendationPriority
    overall_confidence: ConfidenceLevel
    recommendations: list[PerGapRecommendation] = Field(default_factory=list)
    top_recommendation: PerGapRecommendation | None = None
    reasoning: str = ""
    evidence_used: list[ValidatedEvidence] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
