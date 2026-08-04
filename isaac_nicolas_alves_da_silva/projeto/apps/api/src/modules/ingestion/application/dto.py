"""DTOs do módulo de ingestion."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from apps.api.src.modules.ingestion.domain.enums import (
    DocumentSourceType,
    IngestionJobStatus,
)


@dataclass
class CreateIngestionJobInput:
    scraping_result_id: UUID
    source_type: DocumentSourceType = DocumentSourceType.STARTUP_EVIDENCE


@dataclass
class IngestionJobView:
    id: UUID
    scraping_result_id: UUID
    source_type: DocumentSourceType
    status: IngestionJobStatus
    document_id: UUID | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


@dataclass
class ScrapingResultData:
    """Dados do scraping_result lidos pelo port ScrapingResultReader."""

    id: UUID
    job_id: UUID
    url: str
    final_url: str
    title: str | None
    raw_text: str
    quality_score: float
    created_at: datetime
