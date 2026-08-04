"""Caso de uso para consultar o estado de um EmbeddingJob."""

from uuid import UUID

from apps.api.src.modules.embeddings.application.dto import EmbeddingJobView
from apps.api.src.modules.embeddings.application.unit_of_work import (
    EmbeddingsUnitOfWorkFactory,
)
from apps.api.src.modules.embeddings.domain.exceptions import EmbeddingJobNotFoundError


class GetEmbeddingJob:
    def __init__(self, uow_factory: EmbeddingsUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, *, job_id: UUID) -> EmbeddingJobView:
        async with self._uow_factory() as uow:
            job = await uow.job_repository.get_by_id(job_id)
            if job is None:
                raise EmbeddingJobNotFoundError(f"EmbeddingJob {job_id} nao encontrado.")

            return EmbeddingJobView(
                id=job.id,
            document_id=job.document_id,
            status=job.status,
            total_chunks=job.total_chunks,
            succeeded_chunks=job.succeeded_chunks,
            failed_chunks=job.failed_chunks,
            total_latency_ms=job.total_latency_ms,
            total_input_char_count=job.total_input_char_count,
            total_estimated_input_tokens=job.total_estimated_input_tokens,
            error_message=job.error_message,
                created_at=job.created_at,
                started_at=job.started_at,
                finished_at=job.finished_at,
            )
