"""Caso de uso para listar recomendacoes de uma startup."""

from uuid import UUID

from apps.api.src.modules.recommendations.application.dto import RecommendationView
from apps.api.src.modules.recommendations.application.public.recommendations_reader import (
    RecommendationsReader,
)
from apps.api.src.modules.recommendations.application.unit_of_work import (
    RecommendationsUnitOfWorkFactory,
)
from apps.api.src.modules.recommendations.application.use_cases.generate_recommendations import (
    to_recommendation_view,
)


class ListRecommendations(RecommendationsReader):
    """Lista recomendacoes associadas a uma startup."""

    def __init__(self, uow_factory: RecommendationsUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def list_by_startup_id(self, startup_id: UUID) -> list[RecommendationView]:
        async with self._uow_factory() as uow:
            recommendations = await uow.recommendation_repository.list_by_startup_id(
                startup_id
            )

        return [
            to_recommendation_view(recommendation, priority=rank)
            for rank, recommendation in enumerate(recommendations, start=1)
        ]

    async def execute(self, *, startup_id: UUID) -> list[RecommendationView]:
        return await self.list_by_startup_id(startup_id)
