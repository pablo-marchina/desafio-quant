"""Mapper entre ``ScrapingJob`` e ``ScrapingJobModel``."""

from uuid import UUID

from apps.api.src.modules.scraping.domain.entities import ScrapingJob
from apps.api.src.modules.scraping.domain.enums import JobStatus
from apps.api.src.modules.scraping.infrastructure.database.models import (
    ScrapingJobModel,
)


class ScrapingJobMapper:
    """Mantém domínio e SQLAlchemy desacoplados.

    A entidade usa enums e regras de negócio. O model usa tipos adequados ao
    PostgreSQL. O mapper é o ponto explícito de tradução entre os dois mundos.
    """

    @staticmethod
    def to_model(entity: ScrapingJob) -> ScrapingJobModel:
        """Converte uma entidade em um model pronto para persistência."""

        return ScrapingJobModel(
            id=entity.id,
            url=entity.url,
            status=entity.status.value,
            error_message=entity.error_message,
            source_type=entity.source_type,
            created_at=entity.created_at,
            started_at=entity.started_at,
            finished_at=entity.finished_at,
        )

    @staticmethod
    def to_entity(
        model: ScrapingJobModel,
        *,
        result_id: UUID | None = None,
    ) -> ScrapingJob:
        """Converte um registro persistido para a entidade do domínio.

        ``result_id`` não é armazenado em ``scraping_jobs``. O repositório
        poderá obtê-lo consultando ``scraping_results`` pelo ``job_id``.
        """

        return ScrapingJob(
            id=model.id,
            url=model.url,
            status=JobStatus(model.status),
            result_id=result_id,
            error_message=model.error_message,
            source_type=model.source_type,
            created_at=model.created_at,
            started_at=model.started_at,
            finished_at=model.finished_at,
        )

    @staticmethod
    def update_model(model: ScrapingJobModel, entity: ScrapingJob) -> None:
        """Atualiza um model existente sem criar outro registro."""

        model.url = entity.url
        model.status = entity.status.value
        model.error_message = entity.error_message
        model.source_type = entity.source_type
        model.created_at = entity.created_at
        model.started_at = entity.started_at
        model.finished_at = entity.finished_at
