"""Repositorio PostgreSQL para Recommendation."""

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.modules.recommendations.domain.entities import Recommendation
from apps.api.src.modules.recommendations.domain.repositories import (
    RecommendationRepository,
)
from apps.api.src.modules.recommendations.infrastructure.database.mappers.recommendation_mapper import (
    RecommendationMapper,
)
from apps.api.src.modules.recommendations.infrastructure.database.models.recommendation_model import (
    RecommendationModel,
)


class PostgresRecommendationRepository(RecommendationRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, recommendation: Recommendation) -> None:
        self._session.add(RecommendationMapper.to_model(recommendation))
        await self._session.flush()

    async def delete_by_startup_id(self, startup_id: UUID) -> None:
        await self._session.execute(
            delete(RecommendationModel).where(
                RecommendationModel.startup_id == startup_id
            )
        )
        await self._session.flush()

    async def get_by_id(self, recommendation_id: UUID) -> Recommendation | None:
        model = await self._session.get(RecommendationModel, recommendation_id)
        if model is None:
            return None
        return RecommendationMapper.to_entity(model)

    async def list_by_startup_id(self, startup_id: UUID) -> list[Recommendation]:
        models = await self._session.scalars(
            select(RecommendationModel)
            .where(RecommendationModel.startup_id == startup_id)
            .order_by(RecommendationModel.score.desc())
        )
        return [RecommendationMapper.to_entity(model) for model in models]

    async def update_justification(
        self, recommendation_id: UUID, justification: str
    ) -> None:
        model = await self._session.get(RecommendationModel, recommendation_id)
        if model is None:
            return
        model.justification = justification
        await self._session.flush()

    async def update_review(self, recommendation: Recommendation) -> None:
        model = await self._session.get(RecommendationModel, recommendation.id)
        if model is None:
            return
        model.review_status = recommendation.review_status
        model.review_comment = recommendation.review_comment
        model.reviewed_by = recommendation.reviewed_by
        model.reviewed_at = recommendation.reviewed_at
        await self._session.flush()

    async def count_by_technology(self, *, limit: int = 10) -> list[tuple[str, str, int]]:
        statement = (
            select(
                RecommendationModel.technology_slug,
                RecommendationModel.technology_name,
                func.count().label("cnt"),
            )
            .group_by(
                RecommendationModel.technology_slug,
                RecommendationModel.technology_name,
            )
            .order_by(func.count().desc())
            .limit(limit)
        )
        rows = (await self._session.execute(statement)).all()
        return [(row[0], row[1], row[2]) for row in rows]
