"""Caso de uso para buscar uma recomendacao por id."""

from uuid import UUID

from apps.api.src.modules.recommendations.application.dto import RecommendationView
from apps.api.src.modules.recommendations.application.unit_of_work import (
    RecommendationsUnitOfWorkFactory,
)
from apps.api.src.modules.recommendations.application.use_cases.generate_recommendations import (
    to_recommendation_view,
)
from apps.api.src.modules.recommendations.domain.exceptions import (
    RecommendationNotFoundError,
)


class GetRecommendation:
    """Busca uma recomendacao por id."""

    def __init__(self, uow_factory: RecommendationsUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, *, recommendation_id: UUID) -> RecommendationView:
        async with self._uow_factory() as uow:
            recommendation = await uow.recommendation_repository.get_by_id(
                recommendation_id
            )

        if recommendation is None:
            raise RecommendationNotFoundError(
                f"Recomendacao {recommendation_id} nao encontrada."
            )

        return to_recommendation_view(recommendation)
