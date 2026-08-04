"""DTOs do modulo orchestration."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from apps.api.src.modules.orchestration.domain.enums import (
    AnalysisJobStatus,
    UrlIngestionJobStatus,
)


@dataclass(frozen=True)
class CreateAnalysisJobInput:
    startup_id: UUID


@dataclass(frozen=True)
class AnalysisJobView:
    id: UUID
    startup_id: UUID
    status: AnalysisJobStatus
    recommendation_count: int | None
    briefing_id: UUID | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(frozen=True)
class CreateUrlIngestionJobInput:
    url: str
    source_type: str = "startup_evidence"
    startup_id: UUID | None = None
    parent_job_id: UUID | None = None
    enrichment_round: int = 0


@dataclass(frozen=True)
class UrlIngestionJobView:
    id: UUID
    url: str
    source_type: str
    status: UrlIngestionJobStatus
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


@dataclass(frozen=True)
class ListUrlIngestionJobsInput:
    page: int = 1
    page_size: int = 20
    status: UrlIngestionJobStatus | None = None
    source_type: str | None = None


@dataclass(frozen=True)
class UrlIngestionJobPageView:
    items: list[UrlIngestionJobView]
    total: int
    page: int
    page_size: int
