"""Caso de uso para o historico paginado de url ingestion jobs."""

from apps.api.src.modules.orchestration.application.dto import (
    ListUrlIngestionJobsInput,
    UrlIngestionJobPageView,
)
from apps.api.src.modules.orchestration.application.unit_of_work import (
    AnalysisUnitOfWorkFactory,
)
from apps.api.src.modules.orchestration.application.use_cases.create_url_ingestion_job import (
    to_url_ingestion_job_view,
)


class ListUrlIngestionJobs:
    """Lista url ingestion jobs para a tela global de historico."""

    def __init__(self, uow_factory: AnalysisUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self, list_input: ListUrlIngestionJobsInput
    ) -> UrlIngestionJobPageView:
        async with self._uow_factory() as uow:
            jobs, total = await uow.url_ingestion_job_repository.list_page(
                page=list_input.page,
                page_size=list_input.page_size,
                status=list_input.status,
                source_type=list_input.source_type,
            )
        return UrlIngestionJobPageView(
            items=[to_url_ingestion_job_view(job) for job in jobs],
            total=total,
            page=list_input.page,
            page_size=list_input.page_size,
        )
