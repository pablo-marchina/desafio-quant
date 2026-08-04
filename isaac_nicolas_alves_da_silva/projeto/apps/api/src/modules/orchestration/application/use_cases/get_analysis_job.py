"""Caso de uso para buscar um analysis job por id."""

from uuid import UUID

from apps.api.src.modules.orchestration.application.dto import AnalysisJobView
from apps.api.src.modules.orchestration.application.unit_of_work import (
    AnalysisUnitOfWorkFactory,
)
from apps.api.src.modules.orchestration.application.use_cases.execute_analysis_job import (
    to_analysis_job_view,
)
from apps.api.src.modules.orchestration.domain.exceptions import (
    AnalysisJobNotFoundError,
)


class GetAnalysisJob:
    """Busca um analysis job por id."""

    def __init__(self, uow_factory: AnalysisUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, *, analysis_job_id: UUID) -> AnalysisJobView:
        async with self._uow_factory() as uow:
            job = await uow.analysis_job_repository.get_by_id(analysis_job_id)

        if job is None:
            raise AnalysisJobNotFoundError(
                f"Analysis job {analysis_job_id} nao encontrado."
            )

        return to_analysis_job_view(job)
