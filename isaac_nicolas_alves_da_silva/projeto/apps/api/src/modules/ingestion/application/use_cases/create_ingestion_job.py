"""Caso de uso para criar e enfileirar um job de ingestion."""

from apps.api.src.modules.ingestion.application.dto import (
    CreateIngestionJobInput,
    IngestionJobView,
)
from apps.api.src.modules.ingestion.application.ports import IngestionTaskDispatcher
from apps.api.src.modules.ingestion.application.unit_of_work import (
    IngestionUnitOfWorkFactory,
)
from apps.api.src.modules.ingestion.domain.entities import IngestionJob
from apps.api.src.modules.ingestion.domain.exceptions import IngestionTaskDispatchError


class CreateIngestionJob:
    """Persiste um IngestionJob e publica seu id na fila."""

    def __init__(
        self,
        *,
        uow_factory: IngestionUnitOfWorkFactory,
        task_dispatcher: IngestionTaskDispatcher,
    ) -> None:
        self._uow_factory = uow_factory
        self._task_dispatcher = task_dispatcher

    async def execute(self, job_input: CreateIngestionJobInput) -> IngestionJobView:
        job = IngestionJob(
            scraping_result_id=job_input.scraping_result_id,
            source_type=job_input.source_type,
        )

        async with self._uow_factory() as uow:
            await uow.job_repository.save(job)
            await uow.commit()

        try:
            await self._task_dispatcher.dispatch(job_id=job.id)
        except IngestionTaskDispatchError as error:
            async with self._uow_factory() as uow:
                persisted = await uow.job_repository.get_by_id(job.id)
                if persisted is not None:
                    persisted.fail_dispatch(str(error))
                    await uow.job_repository.save(persisted)
                    await uow.commit()
            raise

        return _to_view(job)


def _to_view(job: IngestionJob) -> IngestionJobView:
    return IngestionJobView(
        id=job.id,
        scraping_result_id=job.scraping_result_id,
        source_type=job.source_type,
        status=job.status,
        document_id=job.document_id,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )
