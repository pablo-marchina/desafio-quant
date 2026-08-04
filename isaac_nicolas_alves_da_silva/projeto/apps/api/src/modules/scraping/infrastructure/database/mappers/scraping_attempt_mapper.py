"""Mapper entre ``ScrapingAttempt`` e ``ScrapingAttemptModel``."""

from apps.api.src.modules.scraping.domain.entities import ScrapingAttempt
from apps.api.src.modules.scraping.domain.enums import (
    AttemptStatus,
    ScrapingMethod,
    ValidationDecision,
)
from apps.api.src.modules.scraping.infrastructure.database.models import (
    ScrapingAttemptModel,
)


class ScrapingAttemptMapper:
    """Traduz tentativas entre o domínio e a persistência relacional."""

    @staticmethod
    def to_model(entity: ScrapingAttempt) -> ScrapingAttemptModel:
        """Converte a entidade em um novo model SQLAlchemy."""

        return ScrapingAttemptModel(
            id=entity.id,
            job_id=entity.job_id,
            method=entity.method.value,
            status=entity.status.value,
            decision=entity.decision.value if entity.decision is not None else None,
            technical_score=entity.technical_score,
            text_score=entity.text_score,
            evidence_score=entity.evidence_score,
            quality_score=entity.quality_score,
            problems=list(entity.problems),
            warnings=list(entity.warnings),
            error_message=entity.error_message,
            semantic_confidence=entity.semantic_confidence,
            agent_reviewed=entity.agent_reviewed,
            agent_reason=entity.agent_reason,
            started_at=entity.started_at,
            finished_at=entity.finished_at,
        )

    @staticmethod
    def to_entity(model: ScrapingAttemptModel) -> ScrapingAttempt:
        """Reconstrói a entidade usando os valores armazenados."""

        return ScrapingAttempt(
            id=model.id,
            job_id=model.job_id,
            method=ScrapingMethod(model.method),
            status=AttemptStatus(model.status),
            decision=(
                ValidationDecision(model.decision)
                if model.decision is not None
                else None
            ),
            technical_score=model.technical_score,
            text_score=model.text_score,
            evidence_score=model.evidence_score,
            quality_score=model.quality_score,
            problems=list(model.problems),
            warnings=list(model.warnings),
            error_message=model.error_message,
            semantic_confidence=model.semantic_confidence,
            agent_reviewed=model.agent_reviewed,
            agent_reason=model.agent_reason,
            started_at=model.started_at,
            finished_at=model.finished_at,
        )

    @staticmethod
    def update_model(
        model: ScrapingAttemptModel,
        entity: ScrapingAttempt,
    ) -> None:
        """Atualiza um model existente com o estado atual da entidade."""

        model.job_id = entity.job_id
        model.method = entity.method.value
        model.status = entity.status.value
        model.decision = (
            entity.decision.value if entity.decision is not None else None
        )
        model.technical_score = entity.technical_score
        model.text_score = entity.text_score
        model.evidence_score = entity.evidence_score
        model.quality_score = entity.quality_score
        model.problems = list(entity.problems)
        model.warnings = list(entity.warnings)
        model.error_message = entity.error_message
        model.semantic_confidence = entity.semantic_confidence
        model.agent_reviewed = entity.agent_reviewed
        model.agent_reason = entity.agent_reason
        model.started_at = entity.started_at
        model.finished_at = entity.finished_at
