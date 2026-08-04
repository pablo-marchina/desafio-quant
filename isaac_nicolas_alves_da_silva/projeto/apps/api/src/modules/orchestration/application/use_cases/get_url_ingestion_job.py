"""Caso de uso para consultar um url ingestion job."""

from uuid import UUID

from apps.api.src.modules.orchestration.application.dto import UrlIngestionJobView
from apps.api.src.modules.orchestration.application.unit_of_work import (
    AnalysisUnitOfWorkFactory,
)
from apps.api.src.modules.orchestration.application.use_cases.create_url_ingestion_job import (
    to_url_ingestion_job_view,
)
from apps.api.src.modules.orchestration.domain.exceptions import (
    UrlIngestionJobNotFoundError,
)


class GetUrlIngestionJob:

    def __init__(self, uow_factory: AnalysisUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, *, job_id: UUID) -> UrlIngestionJobView:
        async with self._uow_factory() as uow:
            job = await uow.url_ingestion_job_repository.get_by_id(job_id)
            if job is None:
                raise UrlIngestionJobNotFoundError(
                    f"UrlIngestionJob {job_id} nao encontrado."
                )
            return to_url_ingestion_job_view(job)
