from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


RunStatus = Literal["pending", "running", "completed", "partial", "failed"]
BatchStatus = Literal["pending", "running", "completed", "partial", "failed", "cancelled"]
BatchItemStatus = Literal["pending", "running", "completed", "partial", "failed", "skipped"]
SourceType = Literal["oficial", "imprensa", "ecossistema", "social", "outro"]
SourceStatus = Literal["acessivel", "quebrada", "bloqueada"]
EvidenceClassification = Literal["alta", "media", "baixa"]
AIClassification = Literal["AI-native", "AI-enabled", "API-consumer", "Non-AI"]


class PersistenceModel(BaseModel):
    """Base model shared by all persistence entities."""

    model_config = ConfigDict(extra="forbid")


class Startup(PersistenceModel):
    """Startup persisted as the root entity of pipeline executions."""

    id: UUID | None = None
    external_id: str | None = None
    nome: str = Field(min_length=1)
    site_oficial: HttpUrl | None = None
    categoria: str | None = None
    cidade: str | None = None
    estado: str | None = Field(default=None, min_length=2, max_length=2)
    pais: str = "Brasil"
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PipelineRun(PersistenceModel):
    """Execution state and timing information for one startup investigation."""

    id: UUID | None = None
    startup_id: UUID
    status: RunStatus = "pending"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    current_stage: str | None = None
    trace_path: str | None = None
    errors: list[Any] = Field(default_factory=list)
    warnings: list[Any] = Field(default_factory=list)
    source_errors: list[Any] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SearchQuery(PersistenceModel):
    """Search query generated and executed during one pipeline run."""

    id: UUID | None = None
    pipeline_run_id: UUID
    consulta: str = Field(min_length=1)
    camada: int | None = Field(default=None, ge=1, le=7)
    objetivo: str | None = None
    resultados_count: int = Field(default=0, ge=0)
    created_at: datetime | None = None


class Source(PersistenceModel):
    """Public web source associated with one investigation."""

    id: UUID | None = None
    pipeline_run_id: UUID
    url: HttpUrl
    tipo_fonte: SourceType = "outro"
    credibilidade: float = Field(default=0.0, ge=0.0, le=1.0)
    status: SourceStatus = "acessivel"
    created_at: datetime | None = None


class Evidence(PersistenceModel):
    """Validated or discarded evidence linked to a public source."""

    id: UUID | None = None
    pipeline_run_id: UUID
    source_id: UUID
    trecho: str | None = None
    score_confianca: float = Field(default=0.0, ge=0.0, le=1.0)
    classificacao: EvidenceClassification = "baixa"
    contem_ia: bool = False
    descartada: bool = False
    motivo_descarte: str | None = None
    created_at: datetime | None = None

    @model_validator(mode="after")
    def require_discard_reason(self) -> "Evidence":
        if self.descartada and not self.motivo_descarte:
            raise ValueError("motivo_descarte é obrigatório quando descartada=true")
        return self


class EvidenceInput(PersistenceModel):
    """Combined source and evidence payload accepted by the persistence service."""

    url: HttpUrl
    tipo_fonte: SourceType = "outro"
    credibilidade: float = Field(default=0.0, ge=0.0, le=1.0)
    source_status: SourceStatus = "acessivel"
    trecho: str | None = None
    score_confianca: float = Field(default=0.0, ge=0.0, le=1.0)
    classificacao: EvidenceClassification = "baixa"
    contem_ia: bool = False
    descartada: bool = False
    motivo_descarte: str | None = None

    @model_validator(mode="after")
    def require_discard_reason(self) -> "EvidenceInput":
        if self.descartada and not self.motivo_descarte:
            raise ValueError("motivo_descarte é obrigatório quando descartada=true")
        return self


class AIAssessment(PersistenceModel):
    """Deterministic AI maturity assessment produced by the classifier."""

    id: UUID | None = None
    pipeline_run_id: UUID
    classificacao: AIClassification
    nivel_maturidade: int = Field(ge=0, le=5)
    confianca_classificacao: float = Field(ge=0.0, le=1.0)
    tecnologias_utilizadas: dict[str, Any] = Field(default_factory=dict)
    necessidades: list[str] = Field(default_factory=list)
    justificativa: str = Field(min_length=1)
    evidencias_usadas: list[str] = Field(default_factory=list)
    created_at: datetime | None = None

    @model_validator(mode="after")
    def validate_maturity(self) -> "AIAssessment":
        if self.classificacao == "Non-AI" and self.nivel_maturidade != 0:
            raise ValueError("Non-AI deve usar nivel_maturidade 0")
        if self.classificacao != "Non-AI" and self.nivel_maturidade == 0:
            raise ValueError("classificações com IA devem usar nível entre 1 e 5")
        return self


class InceptionFitAssessment(PersistenceModel):
    """Evidence-aware fit between a startup and the NVIDIA Inception program."""

    id: UUID | None = None
    pipeline_run_id: UUID
    eligibility_status: Literal["eligible", "ineligible", "unknown"]
    startup_stage: Literal["early", "growth", "scale", "unknown"]
    fit_json: dict[str, Any]
    created_at: datetime | None = None


class NVIDIARecommendation(PersistenceModel):
    """Consolidated recommendation payload returned by the NVIDIA RAG."""

    id: UUID | None = None
    pipeline_run_id: UUID
    recomendacao_json: dict[str, Any] = Field(default_factory=dict)
    fit_score: float | None = Field(default=None, ge=0.0, le=1.0)
    created_at: datetime | None = None


class RecommendationCitation(PersistenceModel):
    """Traceable documentation excerpt supporting one NVIDIA recommendation."""

    id: UUID | None = None
    recommendation_id: UUID
    tecnologia: str = Field(min_length=1)
    trecho_doc: str = Field(min_length=1)
    url_doc: HttpUrl
    created_at: datetime | None = None


class RecommendationRefinementRecord(PersistenceModel):
    """Prioritized recommendation package produced after the NVIDIA RAG."""

    id: UUID | None = None
    pipeline_run_id: UUID
    refinement_json: dict[str, Any]
    fit_score: float = Field(ge=0.0, le=1.0)
    created_at: datetime | None = None


class ImpactEstimateRecord(PersistenceModel):
    """Grounded technical and business impact estimate for one run."""

    id: UUID | None = None
    pipeline_run_id: UUID
    impact_json: dict[str, Any]
    aggregate_index: int = Field(ge=0, le=100)
    created_at: datetime | None = None


class ExecutiveBriefingRecord(PersistenceModel):
    """Final executive Markdown generated by the pipeline."""

    id: UUID | None = None
    pipeline_run_id: UUID
    markdown: str = Field(min_length=1, max_length=12000)
    created_at: datetime | None = None


class BatchRun(PersistenceModel):
    """Durable execution state for processing a curated startup collection."""

    id: UUID | None = None
    status: BatchStatus = "pending"
    source_path: str = Field(min_length=1)
    total_items: int = Field(default=0, ge=0)
    processed_items: int = Field(default=0, ge=0)
    succeeded_items: int = Field(default=0, ge=0)
    partial_items: int = Field(default=0, ge=0)
    failed_items: int = Field(default=0, ge=0)
    options: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    worker_id: str | None = None
    heartbeat_at: datetime | None = None
    lease_expires_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class BatchItem(PersistenceModel):
    """One startup investigation belonging to a durable batch run."""

    id: UUID | None = None
    batch_run_id: UUID
    startup_external_id: str = Field(min_length=1)
    startup_name: str = Field(min_length=1)
    startup_payload: dict[str, Any] = Field(default_factory=dict)
    status: BatchItemStatus = "pending"
    pipeline_run_id: UUID | None = None
    attempt_count: int = Field(default=0, ge=0)
    last_error: str | None = None
    result_summary: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class BatchDeadLetter(PersistenceModel):
    """Exhausted batch item retained for diagnosis and explicit replay."""

    id: UUID | None = None
    batch_run_id: UUID
    batch_item_id: UUID
    startup_external_id: str = Field(min_length=1)
    startup_name: str = Field(min_length=1)
    startup_payload: dict[str, Any] = Field(default_factory=dict)
    attempt_count: int = Field(ge=1)
    last_error: str = Field(min_length=1)
    failed_at: datetime | None = None
    resolved_at: datetime | None = None
    created_at: datetime | None = None
