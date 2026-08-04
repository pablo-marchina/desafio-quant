"""Caso de uso para criar e enfileirar um url ingestion job."""

from apps.api.src.modules.orchestration.application.dto import (
    CreateUrlIngestionJobInput,
    UrlIngestionJobView,
)
from apps.api.src.modules.orchestration.application.ports import (
    UrlIngestionTaskDispatcher,
)
from apps.api.src.modules.orchestration.application.unit_of_work import (
    AnalysisUnitOfWorkFactory,
)
from apps.api.src.modules.orchestration.domain.entities import UrlIngestionJob


class CreateUrlIngestionJob:
    """Persiste um UrlIngestionJob pendente e publica seu id na fila.

    A partir daqui, ``AdvanceUrlIngestionJob`` (chamado pelo worker a cada
    entrega da fila) e' quem avanca a maquina de estados um passo por vez.
    """

    def __init__(
        self,
        uow_factory: AnalysisUnitOfWorkFactory,
        task_dispatcher: UrlIngestionTaskDispatcher,
    ) -> None:
        self._uow_factory = uow_factory
        self._task_dispatcher = task_dispatcher

    async def execute(
        self, job_input: CreateUrlIngestionJobInput
    ) -> UrlIngestionJobView:
        job = UrlIngestionJob(
            url=job_input.url,
            source_type=job_input.source_type,
            startup_id=job_input.startup_id,
            parent_job_id=job_input.parent_job_id,
            enrichment_round=job_input.enrichment_round,
        )

        async with self._uow_factory() as uow:
            await uow.url_ingestion_job_repository.save(job)
            await uow.commit()

        await self._task_dispatcher.dispatch(job_id=job.id)

        return to_url_ingestion_job_view(job)


def to_url_ingestion_job_view(job: UrlIngestionJob) -> UrlIngestionJobView:
    return UrlIngestionJobView(
        id=job.id,
        url=job.url,
        source_type=job.source_type,
        status=job.status,
        scraping_job_id=job.scraping_job_id,
        scraping_result_id=job.scraping_result_id,
        ingestion_job_id=job.ingestion_job_id,
        document_id=job.document_id,
        embedding_job_id=job.embedding_job_id,
        startup_id=job.startup_id,
        parent_job_id=job.parent_job_id,
        enrichment_round=job.enrichment_round,
        recommendation_count=job.recommendation_count,
        briefing_id=job.briefing_id,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )
