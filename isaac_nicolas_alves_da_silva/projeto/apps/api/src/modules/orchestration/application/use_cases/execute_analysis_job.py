"""Caso de uso para executar o pipeline recommendations -> briefing.

V1 assume que scraping, ingestion, embeddings e evidencias da startup ja
foram feitos manualmente (fluxo atual). Este orquestrador so encadeia as
duas etapas que ja sao sincronas: gerar recomendacoes e gerar o briefing.
"""

from apps.api.src.modules.orchestration.application.dto import (
    AnalysisJobView,
    CreateAnalysisJobInput,
)
from apps.api.src.modules.orchestration.application.ports import (
    BriefingPort,
    RecommendationsPort,
)
from apps.api.src.modules.orchestration.application.unit_of_work import (
    AnalysisUnitOfWorkFactory,
)
from apps.api.src.modules.orchestration.domain.entities import AnalysisJob


class ExecuteAnalysisJob:
    """Executa e registra uma analise completa de uma startup."""

    def __init__(
        self,
        uow_factory: AnalysisUnitOfWorkFactory,
        recommendations_port: RecommendationsPort,
        briefing_port: BriefingPort,
    ) -> None:
        self._uow_factory = uow_factory
        self._recommendations_port = recommendations_port
        self._briefing_port = briefing_port

    async def execute(self, job_input: CreateAnalysisJobInput) -> AnalysisJobView:
        job = AnalysisJob(startup_id=job_input.startup_id)
        job.start()
        await self._save(job)

        try:
            recommendation_count = await self._recommendations_port.generate(
                job_input.startup_id
            )
            briefing_id = await self._briefing_port.generate(job_input.startup_id)
        except Exception as error:
            job.fail(str(error))
            await self._save(job)
            raise

        job.complete(
            recommendation_count=recommendation_count,
            briefing_id=briefing_id,
        )
        await self._save(job)

        return to_analysis_job_view(job)

    async def _save(self, job: AnalysisJob) -> None:
        async with self._uow_factory() as uow:
            await uow.analysis_job_repository.save(job)
            await uow.commit()


def to_analysis_job_view(job: AnalysisJob) -> AnalysisJobView:
    return AnalysisJobView(
        id=job.id,
        startup_id=job.startup_id,
        status=job.status,
        recommendation_count=job.recommendation_count,
        briefing_id=job.briefing_id,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )
