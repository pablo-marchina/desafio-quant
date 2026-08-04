"""Entidades do dominio do modulo startups."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

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
from apps.api.src.modules.startups.domain.exceptions import InvalidStartupDataError


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class StartupAIProfile:
    """Perfil estruturado de IA extraido das evidencias da startup.

    Cada campo opcional fica em UNKNOWN quando a evidencia nao menciona o
    dado — isso e informacao util no briefing, nao um buraco a ser preenchido
    com chute (anti-alucinacao, regra 9 do CLAUDE.md).

    field_confidence: confianca por nome de campo (0-1).
    field_evidence_ids: evidence_ids por nome de campo que sustentaram o dado.
    """

    ai_workload_type: AiWorkloadType = AiWorkloadType.UNKNOWN
    model_type: AiModelType = AiModelType.UNKNOWN
    data_modality: AiDataModality = AiDataModality.UNKNOWN
    deployment_stage: AiDeploymentStage = AiDeploymentStage.UNKNOWN
    infra_environment: AiInfraEnvironment = AiInfraEnvironment.UNKNOWN
    gpu_need: AiGpuNeed = AiGpuNeed.UNKNOWN
    latency_requirement: AiLatencyRequirement = AiLatencyRequirement.UNKNOWN
    scale_signal: str | None = None
    current_tools: tuple[str, ...] = ()
    business_goal: str | None = None
    field_confidence: dict[str, float] = field(default_factory=dict)
    field_evidence_ids: dict[str, list[str]] = field(default_factory=dict)
    extracted_at: datetime | None = None


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_str_list(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    return tuple(item.strip() for item in values if item.strip())


@dataclass
class Startup:
    """Representacao relacional basica de uma startup."""

    name: str
    website_url: str | None = None
    description: str | None = None
    sector: str | None = None
    country: str | None = None

    ai_maturity_level: AiMaturityLevel | None = None
    classification_reason: str | None = None
    classified_at: datetime | None = None

    founders: tuple[str, ...] = ()
    funding_stage: FundingStage | None = None
    funding_amount_usd: float | None = None
    customers: tuple[str, ...] = ()

    ai_profile: StartupAIProfile | None = None

    # Confianca e evidencias por campo basico extraido (founders, sector, etc.)
    field_confidence: dict[str, float] = field(default_factory=dict)
    field_evidence_ids: dict[str, list[str]] = field(default_factory=dict)

    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        self.website_url = _normalize_optional(self.website_url)
        self.description = _normalize_optional(self.description)
        self.sector = _normalize_optional(self.sector)
        self.country = _normalize_optional(self.country)
        self.founders = _normalize_str_list(self.founders)
        self.customers = _normalize_str_list(self.customers)
        if not self.name:
            raise InvalidStartupDataError("Startup precisa ter nome.")
        if self.funding_amount_usd is not None and self.funding_amount_usd < 0:
            raise InvalidStartupDataError("funding_amount_usd nao pode ser negativo.")

    def update(
        self,
        *,
        name: str | None = None,
        website_url: str | None = None,
        description: str | None = None,
        sector: str | None = None,
        country: str | None = None,
        founders: list[str] | tuple[str, ...] | None = None,
        funding_stage: FundingStage | None = None,
        funding_amount_usd: float | None = None,
        customers: list[str] | tuple[str, ...] | None = None,
    ) -> None:
        if name is not None:
            normalized_name = name.strip()
            if not normalized_name:
                raise InvalidStartupDataError("Startup precisa ter nome.")
            self.name = normalized_name
        if website_url is not None:
            self.website_url = _normalize_optional(website_url)
        if description is not None:
            self.description = _normalize_optional(description)
        if sector is not None:
            self.sector = _normalize_optional(sector)
        if country is not None:
            self.country = _normalize_optional(country)
        if founders is not None:
            self.founders = _normalize_str_list(founders)
        if funding_stage is not None:
            self.funding_stage = funding_stage
        if funding_amount_usd is not None:
            if funding_amount_usd < 0:
                raise InvalidStartupDataError(
                    "funding_amount_usd nao pode ser negativo."
                )
            self.funding_amount_usd = funding_amount_usd
        if customers is not None:
            self.customers = _normalize_str_list(customers)
        self.updated_at = utc_now()

    def update_ai_profile(self, profile: StartupAIProfile) -> None:
        """Registra o perfil estruturado de IA extraido pelo agente."""

        self.ai_profile = profile
        self.updated_at = utc_now()

    def update_field_audit(
        self,
        field_confidence: dict[str, float],
        field_evidence_ids: dict[str, list[str]],
    ) -> None:
        """Registra confianca e evidencias de suporte por campo basico extraido."""

        self.field_confidence = field_confidence
        self.field_evidence_ids = field_evidence_ids
        self.updated_at = utc_now()

    def classify(self, level: AiMaturityLevel, reason: str) -> None:
        """Registra a classificacao de maturidade de IA produzida pelo agente."""

        normalized_reason = reason.strip()
        if not normalized_reason:
            raise InvalidStartupDataError("Classificacao precisa ter justificativa.")

        self.ai_maturity_level = level
        self.classification_reason = normalized_reason
        self.classified_at = utc_now()


@dataclass
class StartupEvidence:
    """Fonte aprovada associada a uma startup."""

    startup_id: UUID
    scraping_result_id: UUID
    source_url: str
    evidence_type: StartupEvidenceType = StartupEvidenceType.OTHER
    title: str | None = None
    confidence_score: float | None = None
    notes: str | None = None

    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.source_url = self.source_url.strip()
        self.title = _normalize_optional(self.title)
        self.notes = _normalize_optional(self.notes)
        if not self.source_url:
            raise InvalidStartupDataError("Evidencia precisa ter source_url.")
        if self.confidence_score is not None and not 0 <= self.confidence_score <= 1:
            raise InvalidStartupDataError(
                "confidence_score deve ficar entre 0 e 1."
            )
