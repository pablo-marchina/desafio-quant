"""DTOs do modulo briefing."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class GenerateBriefingInput:
    startup_id: UUID


@dataclass(frozen=True)
class BriefingView:
    id: UUID
    startup_id: UUID
    content: str
    review_status: str
    review_comment: str | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    generated_at: datetime


@dataclass(frozen=True)
class ReviewBriefingInput:
    briefing_id: UUID
    status: str
    comment: str | None = None
    reviewed_by: str | None = None


@dataclass(frozen=True)
class StartupSnapshot:
    """Perfil da startup, no vocabulario de briefing."""

    name: str
    sector: str | None
    description: str | None
    country: str | None
    website_url: str | None


@dataclass(frozen=True)
class StartupAIProfileSnapshot:
    """Perfil estruturado de IA, no vocabulario de briefing."""

    ai_workload_type: str = "unknown"
    model_type: str = "unknown"
    data_modality: str = "unknown"
    deployment_stage: str = "unknown"
    infra_environment: str = "unknown"
    gpu_need: str = "unknown"
    latency_requirement: str = "unknown"
    scale_signal: str | None = None
    current_tools: tuple[str, ...] = ()
    business_goal: str | None = None
    field_confidence: dict[str, float] | None = None
    field_evidence_ids: dict[str, list[str]] | None = None


@dataclass(frozen=True)
class EvidenceSnapshot:
    """Evidencia da startup, no vocabulario de briefing."""

    title: str | None
    source_url: str
    evidence_type: str
    confidence_score: float | None


@dataclass(frozen=True)
class StartupProfileSnapshot:
    """Perfil completo (startup + evidencias), no vocabulario de briefing."""

    startup: StartupSnapshot
    evidences: tuple[EvidenceSnapshot, ...]
    ai_profile: StartupAIProfileSnapshot | None = None


@dataclass(frozen=True)
class RecommendationSnapshot:
    """Recomendacao NVIDIA, no vocabulario de briefing."""

    technology_name: str
    category: str
    score: float
    justification: str
    confidence: float = 0.0
    complexity: str = "medium"
    nivel: str = "exploratoria"
    faltando: tuple[str, ...] = ()
    signal_origins: tuple[str, ...] = ()
    missing_signals: tuple[str, ...] = ()


@dataclass(frozen=True)
class GroundedContext:
    """Sintese de setor fundamentada em conteudo NVIDIA real, via RAG."""

    text: str
    citation_urls: tuple[str, ...]
