"""Caso de uso para consultar o estado de um IngestionJob."""

from uuid import UUID

from apps.api.src.modules.ingestion.application.dto import IngestionJobView
from apps.api.src.modules.ingestion.application.unit_of_work import (
    IngestionUnitOfWorkFactory,
)
from apps.api.src.modules.ingestion.domain.exceptions import IngestionJobNotFoundError


class GetIngestionJob:
    def __init__(self, uow_factory: IngestionUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, *, job_id: UUID) -> IngestionJobView:
        async with self._uow_factory() as uow:
            job = await uow.job_repository.get_by_id(job_id)
            if job is None:
                raise IngestionJobNotFoundError(
                    f"IngestionJob {job_id} nao encontrado."
                )

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
