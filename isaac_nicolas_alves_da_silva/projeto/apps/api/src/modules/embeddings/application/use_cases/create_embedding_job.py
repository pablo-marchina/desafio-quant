"""Caso de uso para criar e enfileirar um job de embeddings."""

from apps.api.src.modules.embeddings.application.dto import (
    CreateEmbeddingJobInput,
    EmbeddingJobView,
)
from apps.api.src.modules.embeddings.application.ports import EmbeddingTaskDispatcher
from apps.api.src.modules.embeddings.application.unit_of_work import (
    EmbeddingsUnitOfWorkFactory,
)
from apps.api.src.modules.embeddings.domain.entities import EmbeddingJob
from apps.api.src.modules.embeddings.domain.exceptions import EmbeddingTaskDispatchError


class CreateEmbeddingJob:
    """Persiste um EmbeddingJob e publica seu id na fila."""

    def __init__(
        self,
        *,
        uow_factory: EmbeddingsUnitOfWorkFactory,
        task_dispatcher: EmbeddingTaskDispatcher,
    ) -> None:
        self._uow_factory = uow_factory
        self._task_dispatcher = task_dispatcher

    async def execute(self, job_input: CreateEmbeddingJobInput) -> EmbeddingJobView:
        job = EmbeddingJob(document_id=job_input.document_id)

        async with self._uow_factory() as uow:
            await uow.job_repository.save(job)
            await uow.commit()

        try:
            await self._task_dispatcher.dispatch(job_id=job.id)
        except EmbeddingTaskDispatchError as error:
            async with self._uow_factory() as uow:
                persisted = await uow.job_repository.get_by_id(job.id)
                if persisted is not None:
                    persisted.fail(str(error))
                    await uow.job_repository.save(persisted)
                    await uow.commit()
            raise

        return _to_view(job)


def _to_view(job: EmbeddingJob) -> EmbeddingJobView:
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
