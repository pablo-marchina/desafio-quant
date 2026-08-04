"""Mapper entre AnalysisJob e AnalysisJobModel."""

from apps.api.src.modules.orchestration.domain.entities import AnalysisJob
from apps.api.src.modules.orchestration.domain.enums import AnalysisJobStatus
from apps.api.src.modules.orchestration.infrastructure.database.models.analysis_job_model import (
    AnalysisJobModel,
)


class AnalysisJobMapper:

    @staticmethod
    def to_model(entity: AnalysisJob) -> AnalysisJobModel:
        return AnalysisJobModel(
            id=entity.id,
            startup_id=entity.startup_id,
            status=entity.status.value,
            recommendation_count=entity.recommendation_count,
            briefing_id=entity.briefing_id,
            error_message=entity.error_message,
            created_at=entity.created_at,
            started_at=entity.started_at,
            finished_at=entity.finished_at,
        )

    @staticmethod
    def to_entity(model: AnalysisJobModel) -> AnalysisJob:
        return AnalysisJob(
            id=model.id,
            startup_id=model.startup_id,
            status=AnalysisJobStatus(model.status),
            recommendation_count=model.recommendation_count,
            briefing_id=model.briefing_id,
            error_message=model.error_message,
            created_at=model.created_at,
            started_at=model.started_at,
            finished_at=model.finished_at,
        )

    @staticmethod
    def update_model(model: AnalysisJobModel, entity: AnalysisJob) -> None:
        model.status = entity.status.value
        model.recommendation_count = entity.recommendation_count
        model.briefing_id = entity.briefing_id
        model.error_message = entity.error_message
        model.started_at = entity.started_at
        model.finished_at = entity.finished_at
