"""Caso de uso para listar o historico de analysis jobs de uma startup."""

from uuid import UUID

from apps.api.src.modules.orchestration.application.dto import AnalysisJobView
from apps.api.src.modules.orchestration.application.unit_of_work import (
    AnalysisUnitOfWorkFactory,
)
from apps.api.src.modules.orchestration.application.use_cases.execute_analysis_job import (
    to_analysis_job_view,
)


class ListAnalysisJobs:
    """Lista o historico de analysis jobs associados a uma startup."""

    def __init__(self, uow_factory: AnalysisUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, *, startup_id: UUID) -> list[AnalysisJobView]:
        async with self._uow_factory() as uow:
            jobs = await uow.analysis_job_repository.list_by_startup_id(startup_id)

        return [to_analysis_job_view(job) for job in jobs]
