"""Mapper entre UrlIngestionJob e UrlIngestionJobModel."""

from apps.api.src.modules.orchestration.domain.entities import UrlIngestionJob
from apps.api.src.modules.orchestration.domain.enums import UrlIngestionJobStatus
from apps.api.src.modules.orchestration.infrastructure.database.models.url_ingestion_job_model import (
    UrlIngestionJobModel,
)


class UrlIngestionJobMapper:
    @staticmethod
    def to_model(entity: UrlIngestionJob) -> UrlIngestionJobModel:
        return UrlIngestionJobModel(
            id=entity.id,
            url=entity.url,
            source_type=entity.source_type,
            status=entity.status.value,
            scraping_job_id=entity.scraping_job_id,
            scraping_result_id=entity.scraping_result_id,
            ingestion_job_id=entity.ingestion_job_id,
            document_id=entity.document_id,
            embedding_job_id=entity.embedding_job_id,
            startup_id=entity.startup_id,
            parent_job_id=entity.parent_job_id,
            enrichment_round=entity.enrichment_round,
            evidence_attached=entity.evidence_attached,
            recommendations_done=entity.recommendations_done,
            recommendation_count=entity.recommendation_count,
            briefing_id=entity.briefing_id,
            error_message=entity.error_message,
            created_at=entity.created_at,
            started_at=entity.started_at,
            finished_at=entity.finished_at,
        )

    @staticmethod
    def to_entity(model: UrlIngestionJobModel) -> UrlIngestionJob:
        return UrlIngestionJob(
            id=model.id,
            url=model.url,
            source_type=model.source_type,
            status=UrlIngestionJobStatus(model.status),
            scraping_job_id=model.scraping_job_id,
            scraping_result_id=model.scraping_result_id,
            ingestion_job_id=model.ingestion_job_id,
            document_id=model.document_id,
            embedding_job_id=model.embedding_job_id,
            startup_id=model.startup_id,
            parent_job_id=model.parent_job_id,
            enrichment_round=model.enrichment_round,
            evidence_attached=model.evidence_attached,
            recommendations_done=model.recommendations_done,
            recommendation_count=model.recommendation_count,
            briefing_id=model.briefing_id,
            error_message=model.error_message,
            created_at=model.created_at,
            started_at=model.started_at,
            finished_at=model.finished_at,
        )

    @staticmethod
    def update_model(model: UrlIngestionJobModel, entity: UrlIngestionJob) -> None:
        model.url = entity.url
        model.source_type = entity.source_type
        model.status = entity.status.value
        model.scraping_job_id = entity.scraping_job_id
        model.scraping_result_id = entity.scraping_result_id
        model.ingestion_job_id = entity.ingestion_job_id
        model.document_id = entity.document_id
        model.embedding_job_id = entity.embedding_job_id
        model.startup_id = entity.startup_id
        model.parent_job_id = entity.parent_job_id
        model.enrichment_round = entity.enrichment_round
        model.evidence_attached = entity.evidence_attached
        model.recommendations_done = entity.recommendations_done
        model.recommendation_count = entity.recommendation_count
        model.briefing_id = entity.briefing_id
        model.error_message = entity.error_message
        model.started_at = entity.started_at
        model.finished_at = entity.finished_at
