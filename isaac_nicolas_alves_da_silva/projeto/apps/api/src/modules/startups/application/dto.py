"""DTOs do modulo startups."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from apps.api.src.modules.startups.domain.enums import (
    AiDataModality,
    AiDeploymentStage,
    AiGpuNeed,
    AiInfraEnvironment,
    AiLatencyRequirement,
    AiMaturityLevel,
    AiModelType,
    AiWorkloadType,
    FundingStage,
    StartupEvidenceType,
)


@dataclass
class CreateStartupInput:
    name: str
    website_url: str | None = None
    description: str | None = None
    sector: str | None = None
    country: str | None = None


@dataclass
class UpdateStartupInput:
    startup_id: UUID
    name: str | None = None
    website_url: str | None = None
    description: str | None = None
    sector: str | None = None
    country: str | None = None
    founders: list[str] | None = None
    funding_stage: FundingStage | None = None
    funding_amount_usd: float | None = None
    customers: list[str] | None = None


@dataclass
class AddStartupEvidenceInput:
    startup_id: UUID
    scraping_result_id: UUID
    source_url: str
    evidence_type: StartupEvidenceType = StartupEvidenceType.OTHER
    title: str | None = None
    confidence_score: float | None = None
    notes: str | None = None


@dataclass
class ClassifyStartupInput:
    startup_id: UUID


@dataclass
class ExtractStartupProfileInput:
    startup_id: UUID


@dataclass
class StartupAIProfileView:
    """Perfil estruturado de IA da startup, para consumo externo."""

    ai_workload_type: str
    model_type: str
    data_modality: str
    deployment_stage: str
    infra_environment: str
    gpu_need: str
    latency_requirement: str
    scale_signal: str | None
    current_tools: list[str]
    business_goal: str | None
    field_confidence: dict[str, float]
    field_evidence_ids: dict[str, list[str]]
    extracted_at: datetime | None


@dataclass
class StartupView:
    id: UUID
    name: str
    website_url: str | None
    description: str | None
    sector: str | None
    country: str | None
    ai_maturity_level: AiMaturityLevel | None
    classification_reason: str | None
    classified_at: datetime | None
    founders: list[str]
    funding_stage: FundingStage | None
    funding_amount_usd: float | None
    customers: list[str]
    created_at: datetime
    updated_at: datetime
    ai_profile: StartupAIProfileView | None = None
    field_confidence: dict[str, float] = field(default_factory=dict)
    field_evidence_ids: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class ListStartupsInput:
    page: int = 1
    page_size: int = 20
    query: str | None = None
    sector: str | None = None
    country: str | None = None
    ai_maturity_level: AiMaturityLevel | None = None


@dataclass
class StartupPageView:
    items: list[StartupView]
    total: int
    page: int
    page_size: int


@dataclass
class StartupEvidenceView:
    id: UUID
    startup_id: UUID
    scraping_result_id: UUID
    source_url: str
    evidence_type: StartupEvidenceType
    title: str | None
    confidence_score: float | None
    notes: str | None
    created_at: datetime


@dataclass
class StartupProfileView:
    """Perfil completo de uma startup para consumo de outros modulos."""

    startup: StartupView
    evidences: list[StartupEvidenceView]


@dataclass
class MaturityDistributionView:
    """Distribuicao de startups por nivel de maturidade de IA."""

    ai_native: int
    ai_enabled: int
    non_ai: int
    unclassified: int
    total: int
