"""Schemas Pydantic do modulo orchestration."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from apps.api.src.modules.orchestration.application.dto import (
    AnalysisJobView,
    UrlIngestionJobPageView,
    UrlIngestionJobView,
)


class CreateAnalysisJobRequest(BaseModel):
    startup_id: UUID


class AnalysisJobResponse(BaseModel):
    id: UUID
    startup_id: UUID
    status: str
    recommendation_count: int | None
    briefing_id: UUID | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def from_view(cls, view: AnalysisJobView) -> "AnalysisJobResponse":
        return cls(
            id=view.id,
            startup_id=view.startup_id,
            status=view.status.value,
            recommendation_count=view.recommendation_count,
            briefing_id=view.briefing_id,
            error_message=view.error_message,
            created_at=view.created_at,
            started_at=view.started_at,
            finished_at=view.finished_at,
        )


class CreateUrlIngestionJobRequest(BaseModel):
    url: str
    source_type: str = Field(default="startup_evidence")
    startup_id: UUID | None = None


class UrlIngestionJobResponse(BaseModel):
    id: UUID
    url: str
    source_type: str
    status: str
    scraping_job_id: UUID | None
    scraping_result_id: UUID | None
    ingestion_job_id: UUID | None
    document_id: UUID | None
    embedding_job_id: UUID | None
    startup_id: UUID | None
    parent_job_id: UUID | None
    enrichment_round: int
    recommendation_count: int | None
    briefing_id: UUID | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def from_view(cls, view: UrlIngestionJobView) -> "UrlIngestionJobResponse":
        return cls(
            id=view.id,
            url=view.url,
            source_type=view.source_type,
            status=view.status.value,
            scraping_job_id=view.scraping_job_id,
            scraping_result_id=view.scraping_result_id,
            ingestion_job_id=view.ingestion_job_id,
            document_id=view.document_id,
            embedding_job_id=view.embedding_job_id,
            startup_id=view.startup_id,
            parent_job_id=view.parent_job_id,
            enrichment_round=view.enrichment_round,
            recommendation_count=view.recommendation_count,
            briefing_id=view.briefing_id,
            error_message=view.error_message,
            created_at=view.created_at,
            started_at=view.started_at,
            finished_at=view.finished_at,
        )


class UrlIngestionJobPageResponse(BaseModel):
    items: list[UrlIngestionJobResponse]
    total: int
    page: int
    page_size: int

    @classmethod
    def from_view(cls, view: UrlIngestionJobPageView) -> "UrlIngestionJobPageResponse":
        return cls(
            items=[UrlIngestionJobResponse.from_view(item) for item in view.items],
            total=view.total,
            page=view.page,
            page_size=view.page_size,
        )
