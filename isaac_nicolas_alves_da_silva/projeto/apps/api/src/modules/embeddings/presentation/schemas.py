"""Schemas Pydantic da presentation layer do modulo embeddings."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from apps.api.src.modules.embeddings.application.dto import EmbeddingJobView


class CreateEmbeddingJobRequest(BaseModel):
    document_id: UUID


class EmbeddingJobResponse(BaseModel):
    id: UUID
    document_id: UUID
    status: str
    total_chunks: int
    succeeded_chunks: int
    failed_chunks: int
    total_latency_ms: int
    total_input_char_count: int
    total_estimated_input_tokens: int
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def from_view(cls, view: EmbeddingJobView) -> "EmbeddingJobResponse":
        return cls(
            id=view.id,
            document_id=view.document_id,
            status=view.status.value,
            total_chunks=view.total_chunks,
            succeeded_chunks=view.succeeded_chunks,
            failed_chunks=view.failed_chunks,
            total_latency_ms=view.total_latency_ms,
            total_input_char_count=view.total_input_char_count,
            total_estimated_input_tokens=view.total_estimated_input_tokens,
            error_message=view.error_message,
            created_at=view.created_at,
            started_at=view.started_at,
            finished_at=view.finished_at,
        )
