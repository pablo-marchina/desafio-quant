"""Mapper entre EmbeddingJobChunk e EmbeddingJobChunkModel."""

from apps.api.src.modules.embeddings.domain.entities import EmbeddingJobChunk
from apps.api.src.modules.embeddings.domain.enums import EmbeddingJobChunkStatus
from apps.api.src.modules.embeddings.infrastructure.database.models.embedding_job_chunk_model import (
    EmbeddingJobChunkModel,
)


class EmbeddingJobChunkMapper:

    @staticmethod
    def to_model(entity: EmbeddingJobChunk) -> EmbeddingJobChunkModel:
        return EmbeddingJobChunkModel(
            id=entity.id,
            job_id=entity.job_id,
            chunk_id=entity.chunk_id,
            content_hash=entity.content_hash,
            status=entity.status.value,
            attempt_count=entity.attempt_count,
            model_name=entity.model_name,
            vector_dimension=entity.vector_dimension,
            input_char_count=entity.input_char_count,
            estimated_input_tokens=entity.estimated_input_tokens,
            latency_ms=entity.latency_ms,
            error_message=entity.error_message,
            created_at=entity.created_at,
            finished_at=entity.finished_at,
        )

    @staticmethod
    def to_entity(model: EmbeddingJobChunkModel) -> EmbeddingJobChunk:
        return EmbeddingJobChunk(
            id=model.id,
            job_id=model.job_id,
            chunk_id=model.chunk_id,
            content_hash=model.content_hash,
            status=EmbeddingJobChunkStatus(model.status),
            attempt_count=model.attempt_count,
            model_name=model.model_name,
            vector_dimension=model.vector_dimension,
            input_char_count=model.input_char_count,
            estimated_input_tokens=model.estimated_input_tokens,
            latency_ms=model.latency_ms,
            error_message=model.error_message,
            created_at=model.created_at,
            finished_at=model.finished_at,
        )

    @staticmethod
    def update_model(model: EmbeddingJobChunkModel, entity: EmbeddingJobChunk) -> None:
        model.content_hash = entity.content_hash
        model.status = entity.status.value
        model.attempt_count = entity.attempt_count
        model.model_name = entity.model_name
        model.vector_dimension = entity.vector_dimension
        model.input_char_count = entity.input_char_count
        model.estimated_input_tokens = entity.estimated_input_tokens
        model.latency_ms = entity.latency_ms
        model.error_message = entity.error_message
        model.finished_at = entity.finished_at
