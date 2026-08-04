"""Mapper entre IngestionJob e IngestionJobModel."""

from apps.api.src.modules.ingestion.domain.entities import IngestionJob
from apps.api.src.modules.ingestion.domain.enums import (
    DocumentSourceType,
    IngestionJobStatus,
)
from apps.api.src.modules.ingestion.infrastructure.database.models.ingestion_job_model import (
    IngestionJobModel,
)


class IngestionJobMapper:

    @staticmethod
    def to_model(entity: IngestionJob) -> IngestionJobModel:
        return IngestionJobModel(
            id=entity.id,
            scraping_result_id=entity.scraping_result_id,
            source_type=entity.source_type.value,
            status=entity.status.value,
            document_id=entity.document_id,
            error_message=entity.error_message,
            created_at=entity.created_at,
            started_at=entity.started_at,
            finished_at=entity.finished_at,
        )

    @staticmethod
    def to_entity(model: IngestionJobModel) -> IngestionJob:
        return IngestionJob(
            id=model.id,
            scraping_result_id=model.scraping_result_id,
            source_type=DocumentSourceType(model.source_type),
            status=IngestionJobStatus(model.status),
            document_id=model.document_id,
            error_message=model.error_message,
            created_at=model.created_at,
            started_at=model.started_at,
            finished_at=model.finished_at,
        )

    @staticmethod
    def update_model(model: IngestionJobModel, entity: IngestionJob) -> None:
        model.scraping_result_id = entity.scraping_result_id
        model.source_type = entity.source_type.value
        model.status = entity.status.value
        model.document_id = entity.document_id
        model.error_message = entity.error_message
        model.started_at = entity.started_at
        model.finished_at = entity.finished_at
