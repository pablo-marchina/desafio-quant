"""Mapper entre Recommendation e RecommendationModel."""

from uuid import UUID

from apps.api.src.modules.recommendations.domain.entities import Recommendation
from apps.api.src.modules.recommendations.infrastructure.database.models.recommendation_model import (
    RecommendationModel,
)


class RecommendationMapper:

    @staticmethod
    def to_model(entity: Recommendation) -> RecommendationModel:
        return RecommendationModel(
            id=entity.id,
            startup_id=entity.startup_id,
            technology_slug=entity.technology_slug,
            technology_name=entity.technology_name,
            category=entity.category,
            score=entity.score,
            confidence=entity.confidence,
            complexity=entity.complexity,
            justification=entity.justification,
            matched_keywords=list(entity.matched_keywords),
            evidence_ids=[str(evidence_id) for evidence_id in entity.evidence_ids],
            signal_origins=list(entity.signal_origins),
            missing_signals=list(entity.missing_signals),
            nivel=entity.nivel,
            faltando=list(entity.faltando),
            review_status=entity.review_status,
            review_comment=entity.review_comment,
            reviewed_by=entity.reviewed_by,
            reviewed_at=entity.reviewed_at,
            created_at=entity.created_at,
        )

    @staticmethod
    def to_entity(model: RecommendationModel) -> Recommendation:
        return Recommendation(
            id=model.id,
            startup_id=model.startup_id,
            technology_slug=model.technology_slug,
            technology_name=model.technology_name,
            category=model.category,
            score=model.score,
            confidence=model.confidence,
            complexity=model.complexity,
            justification=model.justification,
            matched_keywords=tuple(model.matched_keywords),
            evidence_ids=tuple(UUID(value) for value in model.evidence_ids),
            signal_origins=tuple(model.signal_origins or []),
            missing_signals=tuple(model.missing_signals or []),
            nivel=model.nivel or "exploratoria",
            faltando=tuple(model.faltando or []),
            review_status=model.review_status,
            review_comment=model.review_comment,
            reviewed_by=model.reviewed_by,
            reviewed_at=model.reviewed_at,
            created_at=model.created_at,
        )
