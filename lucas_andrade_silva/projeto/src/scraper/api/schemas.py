from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobAccepted(BaseModel):
    job_id: str
    status: JobStatus


class NvidiaRecommendationRequest(BaseModel):
    need: str | None = Field(default=None, max_length=1000)


class CompetitiveAnalysisRequest(BaseModel):
    question: str | None = Field(default=None, max_length=1000)


class ActionReportRequest(BaseModel):
    objective: str | None = Field(default=None, max_length=1000)
    context: dict[str, Any] | None = None


class JobResponse(JobAccepted):
    job_type: str
    startup_id: str
    progress: int = Field(ge=0, le=100)
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    result: Any = None


class HealthResponse(BaseModel):
    status: str
    service: str


class StartupListResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int
    page: int
    page_size: int


class StartupResponse(BaseModel):
    startup: dict[str, Any]


ValidationStatus = Literal[
    "APPROVED",
    "REVIEW",
    "REJECTED",
    "DISCARDED",
    "Ativa",
    "Baixada",
    "Inapta",
    "Suspensa",
    "Nula",
]
EnrichmentStatus = Literal[
    "enriched",
    "needs_review",
    "insufficient_evidence",
    "error",
    "discarded",
    "scraped",
]
AiDependencyLevel = Literal[
    "AI_NATIVE",
    "AI_ENABLED",
    "NON_AI",
    "AI_MENTIONED",
    "NO_SIGNAL",
    "INSUFFICIENT_EVIDENCE",
]


class StartupCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(min_length=1)
    company_name: str = Field(min_length=1, max_length=300)
    website: str | None = None
    description: str | None = None
    technology_intelligence: dict[str, Any] | None = None
    nvidia_recommendation: dict[str, Any] | None = None
    competitive_analysis: dict[str, Any] | None = None
    action_report: dict[str, Any] | None = None
    ai_dependency_level: AiDependencyLevel = "INSUFFICIENT_EVIDENCE"
    enrichment_status: EnrichmentStatus = "needs_review"
    cnpj: str | None = None
    cnae: str | None = None
    socios: list[dict[str, Any]] = Field(default_factory=list)
    cnpj_data: dict[str, Any] = Field(default_factory=dict)
    founding_year: str = "Not specified"
    location: str = "Brazil"
    ai_technology_focus: str = "Unknown"
    target_market: str | None = None
    key_milestones: str | None = None
    validation_status: ValidationStatus | None = None
    is_active: bool = True


class StartupUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: str | None = Field(default=None, min_length=1, max_length=300)
    website: str | None = None
    description: str | None = None
    technology_intelligence: dict[str, Any] | None = None
    nvidia_recommendation: dict[str, Any] | None = None
    competitive_analysis: dict[str, Any] | None = None
    action_report: dict[str, Any] | None = None
    ai_dependency_level: AiDependencyLevel | None = None
    enrichment_status: EnrichmentStatus | None = None
    cnpj: str | None = None
    cnae: str | None = None
    socios: list[dict[str, Any]] | None = None
    cnpj_data: dict[str, Any] | None = None
    founding_year: str | None = None
    location: str | None = None
    ai_technology_focus: str | None = None
    target_market: str | None = None
    key_milestones: str | None = None
    validation_status: ValidationStatus | None = None
    is_active: bool | None = None


class GithubActionsRegistrationPoint(BaseModel):
    date: str
    weekday: Literal["Seg", "Qui"]
    count: int = Field(ge=0)


class DashboardSummaryResponse(BaseModel):
    total_startups: int
    validation_statuses: dict[str, int]
    enrichment_statuses: dict[str, int]
    ai_classifications: dict[str, int]
    recommendations_count: int = 0
    github_actions_registrations: list[GithubActionsRegistrationPoint] = (
        Field(default_factory=list)
    )
    generated_at: datetime
