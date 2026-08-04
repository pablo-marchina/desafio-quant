"""Mapper entre StartupEvidence e StartupEvidenceModel."""

from apps.api.src.modules.startups.domain.entities import StartupEvidence
from apps.api.src.modules.startups.domain.enums import StartupEvidenceType
from apps.api.src.modules.startups.infrastructure.database.models.startup_evidence_model import (
    StartupEvidenceModel,
)


class StartupEvidenceMapper:

    @staticmethod
    def to_model(entity: StartupEvidence) -> StartupEvidenceModel:
        return StartupEvidenceModel(
            id=entity.id,
            startup_id=entity.startup_id,
            scraping_result_id=entity.scraping_result_id,
            source_url=entity.source_url,
            evidence_type=entity.evidence_type.value,
            title=entity.title,
            confidence_score=entity.confidence_score,
            notes=entity.notes,
            created_at=entity.created_at,
        )

    @staticmethod
    def to_entity(model: StartupEvidenceModel) -> StartupEvidence:
        return StartupEvidence(
            id=model.id,
            startup_id=model.startup_id,
            scraping_result_id=model.scraping_result_id,
            source_url=model.source_url,
            evidence_type=StartupEvidenceType(model.evidence_type),
            title=model.title,
            confidence_score=model.confidence_score,
            notes=model.notes,
            created_at=model.created_at,
        )

    @staticmethod
    def update_model(
        model: StartupEvidenceModel, entity: StartupEvidence
    ) -> None:
        model.startup_id = entity.startup_id
        model.scraping_result_id = entity.scraping_result_id
        model.source_url = entity.source_url
        model.evidence_type = entity.evidence_type.value
        model.title = entity.title
        model.confidence_score = entity.confidence_score
        model.notes = entity.notes
