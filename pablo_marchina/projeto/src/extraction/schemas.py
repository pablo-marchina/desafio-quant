"""Core data contracts for startup profiles, evidence, and recommendations."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl

from src.quantitative.params import CONFIDENCE_THRESHOLDS


class SourceType(str, Enum):
    OFFICIAL_SITE = "official_site"
    NEWS = "news"
    DIRECTORY = "directory"
    BLOG = "blog"
    JOB_POST = "job_post"
    FOUNDER_PROFILE = "founder_profile"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @classmethod
    def from_score(cls, score: float) -> ConfidenceLevel:
        if score >= CONFIDENCE_THRESHOLDS["high_min"]:
            return cls.HIGH
        if score >= CONFIDENCE_THRESHOLDS["medium_min"]:
            return cls.MEDIUM
        return cls.LOW


class AINativeLevel(str, Enum):
    NON_AI = "non_ai"
    AI_ASSISTED = "ai_assisted"
    AI_ENABLED = "ai_enabled"
    AI_NATIVE = "ai_native"
    AI_NATIVE_SERVICE = "ai_native_service"


class TechnicalGap(str, Enum):
    EXTERNAL_API_DEPENDENCY = "external_api_dependency"
    HIGH_INFERENCE_COST = "high_inference_cost"
    HIGH_LATENCY = "high_latency"
    AGENT_GOVERNANCE_GAP = "agent_governance_gap"
    OBSERVABILITY_GAP = "observability_gap"
    MODEL_EVALUATION_GAP = "model_evaluation_gap"
    PRIVACY_OR_CONTROLLED_DEPLOYMENT_GAP = "privacy_or_controlled_deployment_gap"
    SLOW_DATA_PIPELINE = "slow_data_pipeline"
    HEAVY_TABULAR_PROCESSING = "heavy_tabular_processing"
    VOICE_NEED = "voice_need"
    SIMULATION_NEED = "simulation_need"
    COMPUTER_VISION_NEED = "computer_vision_need"
    ROBOTICS_NEED = "robotics_need"
    HEALTHCARE_COMPLIANCE_NEED = "healthcare_compliance_need"
    AI_CYBERSECURITY_NEED = "ai_cybersecurity_need"


class RecommendationPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ImplementationComplexity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Evidence(BaseModel):
    claim: str
    source_url: HttpUrl
    source_type: SourceType
    quote_or_evidence: str
    confidence: ConfidenceLevel
    collected_at: datetime
    source_quality_score: float | None = None
    evidence_confidence_score: float | None = None
    score_status: str | None = None
    score_features: dict[str, float] | None = None
    score_calibration_decision_ids: list[str] | None = None


class StartupProfile(BaseModel):
    startup_name: str
    website: HttpUrl
    country: str = "Brazil"
    sector: str
    description: str
    product_summary: str
    ai_signals: list[str] = Field(default_factory=list)
    customers: list[str] = Field(default_factory=list)
    founders: list[str] = Field(default_factory=list)
    funding_signals: list[str] = Field(default_factory=list)
    tech_stack_signals: list[str] = Field(default_factory=list)
    sources: list[Evidence] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0)
