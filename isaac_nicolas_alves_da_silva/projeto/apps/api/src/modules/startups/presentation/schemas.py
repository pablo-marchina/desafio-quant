"""Schemas Pydantic do modulo startups."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from apps.api.src.modules.startups.application.dto import (
    MaturityDistributionView,
    StartupAIProfileView,
    StartupEvidenceView,
    StartupPageView,
    StartupView,
)
from apps.api.src.modules.startups.domain.enums import FundingStage, StartupEvidenceType


class CreateStartupRequest(BaseModel):
    name: str
    website_url: str | None = None
    description: str | None = None
    sector: str | None = None
    country: str | None = None


class UpdateStartupRequest(BaseModel):
    name: str | None = None
    website_url: str | None = None
    description: str | None = None
    sector: str | None = None
    country: str | None = None
    founders: list[str] | None = None
    funding_stage: FundingStage | None = None
    funding_amount_usd: float | None = None
    customers: list[str] | None = None


class AddStartupEvidenceRequest(BaseModel):
    scraping_result_id: UUID
    source_url: str
    evidence_type: StartupEvidenceType = StartupEvidenceType.OTHER
    title: str | None = None
    confidence_score: float | None = None
    notes: str | None = None


class StartupAIProfileResponse(BaseModel):
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

    @classmethod
    def from_view(cls, view: StartupAIProfileView) -> "StartupAIProfileResponse":
        return cls(
            ai_workload_type=view.ai_workload_type,
            model_type=view.model_type,
            data_modality=view.data_modality,
            deployment_stage=view.deployment_stage,
            infra_environment=view.infra_environment,
            gpu_need=view.gpu_need,
            latency_requirement=view.latency_requirement,
            scale_signal=view.scale_signal,
            current_tools=view.current_tools,
            business_goal=view.business_goal,
            field_confidence=view.field_confidence,
            field_evidence_ids=view.field_evidence_ids,
            extracted_at=view.extracted_at,
        )


class StartupResponse(BaseModel):
    id: UUID
    name: str
    website_url: str | None
    description: str | None
    sector: str | None
    country: str | None
    ai_maturity_level: str | None
    classification_reason: str | None
    classified_at: datetime | None
    founders: list[str]
    funding_stage: str | None
    funding_amount_usd: float | None
    customers: list[str]
    created_at: datetime
    updated_at: datetime
    ai_profile: StartupAIProfileResponse | None = None
    field_confidence: dict[str, float] = {}
    field_evidence_ids: dict[str, list[str]] = {}

    @classmethod
    def from_view(cls, view: StartupView) -> "StartupResponse":
        return cls(
            id=view.id,
            name=view.name,
            website_url=view.website_url,
            description=view.description,
            sector=view.sector,
            country=view.country,
            ai_maturity_level=(
                view.ai_maturity_level.value
                if view.ai_maturity_level is not None
                else None
            ),
            classification_reason=view.classification_reason,
            classified_at=view.classified_at,
            founders=view.founders,
            funding_stage=(
                view.funding_stage.value if view.funding_stage is not None else None
            ),
            funding_amount_usd=view.funding_amount_usd,
            customers=view.customers,
            created_at=view.created_at,
            updated_at=view.updated_at,
            ai_profile=(
                StartupAIProfileResponse.from_view(view.ai_profile)
                if view.ai_profile is not None
                else None
            ),
            field_confidence=view.field_confidence,
            field_evidence_ids=view.field_evidence_ids,
        )


class StartupEvidenceResponse(BaseModel):
    id: UUID
    startup_id: UUID
    scraping_result_id: UUID
    source_url: str
    evidence_type: str
    title: str | None
    confidence_score: float | None
    notes: str | None
    created_at: datetime

    @classmethod
    def from_view(cls, view: StartupEvidenceView) -> "StartupEvidenceResponse":
        return cls(
            id=view.id,
            startup_id=view.startup_id,
            scraping_result_id=view.scraping_result_id,
            source_url=view.source_url,
            evidence_type=view.evidence_type.value,
            title=view.title,
            confidence_score=view.confidence_score,
            notes=view.notes,
            created_at=view.created_at,
        )


class StartupPageResponse(BaseModel):
    items: list[StartupResponse]
    total: int
    page: int
    page_size: int

    @classmethod
    def from_view(cls, view: StartupPageView) -> "StartupPageResponse":
        return cls(
            items=[StartupResponse.from_view(item) for item in view.items],
            total=view.total,
            page=view.page,
            page_size=view.page_size,
        )


class MaturityDistributionResponse(BaseModel):
    ai_native: int
    ai_enabled: int
    non_ai: int
    unclassified: int
    total: int

    @classmethod
    def from_view(cls, view: MaturityDistributionView) -> "MaturityDistributionResponse":
        return cls(
            ai_native=view.ai_native,
            ai_enabled=view.ai_enabled,
            non_ai=view.non_ai,
            unclassified=view.unclassified,
            total=view.total,
        )
