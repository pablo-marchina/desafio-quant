"""Mapper entre EmbeddingJob e EmbeddingJobModel."""

from apps.api.src.modules.embeddings.domain.entities import EmbeddingJob
from apps.api.src.modules.embeddings.domain.enums import EmbeddingJobStatus
from apps.api.src.modules.embeddings.infrastructure.database.models.embedding_job_model import (
    EmbeddingJobModel,
)


class EmbeddingJobMapper:

    @staticmethod
    def to_model(entity: EmbeddingJob) -> EmbeddingJobModel:
        return EmbeddingJobModel(
            id=entity.id,
            document_id=entity.document_id,
            status=entity.status.value,
            total_chunks=entity.total_chunks,
            succeeded_chunks=entity.succeeded_chunks,
            failed_chunks=entity.failed_chunks,
            total_latency_ms=entity.total_latency_ms,
            total_input_char_count=entity.total_input_char_count,
            total_estimated_input_tokens=entity.total_estimated_input_tokens,
            error_message=entity.error_message,
            created_at=entity.created_at,
            started_at=entity.started_at,
            finished_at=entity.finished_at,
        )

    @staticmethod
    def to_entity(model: EmbeddingJobModel) -> EmbeddingJob:
        return EmbeddingJob(
            id=model.id,
            document_id=model.document_id,
            status=EmbeddingJobStatus(model.status),
            total_chunks=model.total_chunks,
            succeeded_chunks=model.succeeded_chunks,
            failed_chunks=model.failed_chunks,
            total_latency_ms=model.total_latency_ms,
            total_input_char_count=model.total_input_char_count,
            total_estimated_input_tokens=model.total_estimated_input_tokens,
            error_message=model.error_message,
            created_at=model.created_at,
            started_at=model.started_at,
            finished_at=model.finished_at,
        )

    @staticmethod
    def update_model(model: EmbeddingJobModel, entity: EmbeddingJob) -> None:
        model.document_id = entity.document_id
        model.status = entity.status.value
        model.total_chunks = entity.total_chunks
        model.succeeded_chunks = entity.succeeded_chunks
        model.failed_chunks = entity.failed_chunks
        model.total_latency_ms = entity.total_latency_ms
        model.total_input_char_count = entity.total_input_char_count
        model.total_estimated_input_tokens = entity.total_estimated_input_tokens
        model.error_message = entity.error_message
        model.started_at = entity.started_at
        model.finished_at = entity.finished_at
