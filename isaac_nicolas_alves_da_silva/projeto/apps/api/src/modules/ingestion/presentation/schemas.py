"""Schemas Pydantic da presentation layer do módulo de ingestion."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from apps.api.src.modules.ingestion.application.dto import IngestionJobView
from apps.api.src.modules.ingestion.domain.enums import DocumentSourceType


class CreateIngestionJobRequest(BaseModel):
    scraping_result_id: UUID
    source_type: DocumentSourceType = DocumentSourceType.STARTUP_EVIDENCE


class IngestionJobResponse(BaseModel):
    id: UUID
    scraping_result_id: UUID
    source_type: str
    status: str
    document_id: UUID | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def from_view(cls, view: IngestionJobView) -> "IngestionJobResponse":
        return cls(
            id=view.id,
            scraping_result_id=view.scraping_result_id,
            source_type=view.source_type.value,
            status=view.status.value,
            document_id=view.document_id,
            error_message=view.error_message,
            created_at=view.created_at,
            started_at=view.started_at,
            finished_at=view.finished_at,
        )
