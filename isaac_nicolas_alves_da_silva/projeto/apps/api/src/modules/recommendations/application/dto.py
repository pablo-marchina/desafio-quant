"""DTOs do modulo recommendations."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class GenerateRecommendationsInput:
    startup_id: UUID


@dataclass(frozen=True)
class RecommendationView:
    id: UUID
    startup_id: UUID
    technology_slug: str
    technology_name: str
    category: str
    score: float
    confidence: float
    complexity: str
    priority: int
    justification: str
    matched_keywords: list[str]
    evidence_ids: list[UUID]
    review_status: str
    review_comment: str | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    created_at: datetime
    signal_origins: list[str] = field(default_factory=list)
    missing_signals: list[str] = field(default_factory=list)
    nivel: str = "exploratoria"
    faltando: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ReviewRecommendationInput:
    recommendation_id: UUID
    status: str
    comment: str | None = None
    reviewed_by: str | None = None


@dataclass(frozen=True)
class EvidenceSnapshot:
    """Evidencia de uma startup, no vocabulario de recommendations."""

    evidence_id: UUID
    title: str | None
    notes: str | None
    confidence_score: float = 0.5
    source_url: str | None = None
    evidence_type: str | None = None


@dataclass(frozen=True)
class AIProfileSnapshot:
    """Subconjunto do StartupAIProfile necessario para o score composto.

    Vocabulario deste modulo — nao importa enums do modulo startups.
    Traducao e responsabilidade do adapter em infrastructure/startups_adapters/.
    """

    ai_workload_type: str = "unknown"
    deployment_stage: str = "unknown"
    gpu_need: str = "unknown"
    has_operational_signal: bool = False
    profile_strength: float = 0.0


@dataclass(frozen=True)
class StartupProfileSnapshot:
    """Perfil minimo de startup necessario para gerar recomendacoes."""

    sector: str | None
    description: str | None
    evidences: tuple[EvidenceSnapshot, ...]
    ai_maturity_level: str | None = None
    ai_profile: AIProfileSnapshot | None = None


@dataclass(frozen=True)
class NvidiaTechnologySnapshot:
    """Tecnologia NVIDIA, no vocabulario de recommendations."""

    slug: str
    name: str
    category: str
    use_cases: tuple[str, ...]
    keywords: tuple[str, ...]
    complexity: str = "medium"
    supported_workloads: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class GroundedJustification:
    """Justificativa fundamentada em conteudo NVIDIA real, via RAG."""

    text: str
    citation_urls: tuple[str, ...]


@dataclass(frozen=True)
class TechnologyStatView:
    """Contagem de startups recomendadas para uma tecnologia NVIDIA."""

    technology_slug: str
    technology_name: str
    count: int


@dataclass(frozen=True)
class TechnologyStatsView:
    """Top tecnologias NVIDIA mais recomendadas no portfolio."""

    items: list[TechnologyStatView]
