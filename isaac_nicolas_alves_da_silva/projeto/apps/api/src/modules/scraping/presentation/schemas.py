"""Schemas dos JSONs recebidos e retornados pela API de scraping."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from apps.api.src.modules.scraping.domain.entities import (
    ScrapingAttempt,
    ScrapingJob,
    ScrapingResult,
)
from apps.api.src.modules.scraping.domain.enums import (
    AttemptStatus,
    JobStatus,
    ScrapingMethod,
    ValidationDecision,
)


class CreateScrapingJobRequest(BaseModel):
    """JSON recebido ao solicitar a criação de um job."""

    # HttpUrl faz uma validação inicial de formato. A proteção SSRF mais forte
    # continua sendo responsabilidade do UrlGuard antes da requisição real.
    url: HttpUrl


class ScrapingJobResponse(BaseModel):
    """Representação pública de um job."""

    id: UUID
    url: str
    status: JobStatus
    result_id: UUID | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def from_entity(cls, job: ScrapingJob) -> "ScrapingJobResponse":
        """Converte a entidade sem acoplar a rota aos detalhes dos campos."""

        return cls(
            id=job.id,
            url=job.url,
            status=job.status,
            result_id=job.result_id,
            error_message=job.error_message,
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
        )


class ScrapingAttemptResponse(BaseModel):
    """Representação pública de uma tentativa de coleta."""

    id: UUID
    method: ScrapingMethod
    status: AttemptStatus
    decision: ValidationDecision | None
    technical_score: float | None
    text_score: float | None
    evidence_score: float | None
    quality_score: float | None
    problems: list[str]
    warnings: list[str]
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None

    @classmethod
    def from_entity(cls, attempt: ScrapingAttempt) -> "ScrapingAttemptResponse":
        return cls(
            id=attempt.id,
            method=attempt.method,
            status=attempt.status,
            decision=attempt.decision,
            technical_score=attempt.technical_score,
            text_score=attempt.text_score,
            evidence_score=attempt.evidence_score,
            quality_score=attempt.quality_score,
            problems=attempt.problems,
            warnings=attempt.warnings,
            error_message=attempt.error_message,
            started_at=attempt.started_at,
            finished_at=attempt.finished_at,
        )


class ScrapingJobDetailsResponse(BaseModel):
    """Resposta da consulta de um job junto com seu histórico."""

    job: ScrapingJobResponse
    attempts: list[ScrapingAttemptResponse]


class ScrapingResultResponse(BaseModel):
    """Representação pública do conteúdo bruto aprovado."""

    model_config = ConfigDict(protected_namespaces=())

    id: UUID
    job_id: UUID
    url: str
    final_url: str
    title: str | None

    # O HTML pode ser grande. Mantemos o campo porque esta primeira entrega
    # precisa demonstrar o conteúdo bruto coletado.
    raw_html: str
    raw_text: str

    method: ScrapingMethod
    status_code: int
    technical_score: float = Field(ge=0, le=1)
    text_score: float = Field(ge=0, le=1)
    evidence_score: float = Field(ge=0, le=1)
    quality_score: float = Field(ge=0, le=1)
    content_hash: str
    metadata: dict[str, str | int | float | bool | None]
    created_at: datetime

    @classmethod
    def from_entity(cls, result: ScrapingResult) -> "ScrapingResultResponse":
        return cls(
            id=result.id,
            job_id=result.job_id,
            url=result.url,
            final_url=result.final_url,
            title=result.title,
            raw_html=result.raw_html,
            raw_text=result.raw_text,
            method=result.method,
            status_code=result.status_code,
            technical_score=result.technical_score,
            text_score=result.text_score,
            evidence_score=result.evidence_score,
            quality_score=result.quality_score,
            content_hash=result.content_hash,
            metadata=result.metadata,
            created_at=result.created_at,
        )
