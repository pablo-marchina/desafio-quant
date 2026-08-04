"""Caso de uso para registrar revisao humana de uma recomendacao."""

from apps.api.src.modules.recommendations.application.dto import (
    RecommendationView,
    ReviewRecommendationInput,
)
from apps.api.src.modules.recommendations.application.unit_of_work import (
    RecommendationsUnitOfWorkFactory,
)
from apps.api.src.modules.recommendations.application.use_cases.generate_recommendations import (
    to_recommendation_view,
)
from apps.api.src.modules.recommendations.domain.exceptions import (
    RecommendationNotFoundError,
)


class ReviewRecommendation:
    """Aprova/rejeita uma recomendacao sem exigir auth completa."""

    def __init__(self, uow_factory: RecommendationsUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, review_input: ReviewRecommendationInput) -> RecommendationView:
        async with self._uow_factory() as uow:
            recommendation = await uow.recommendation_repository.get_by_id(
                review_input.recommendation_id
            )
            if recommendation is None:
                raise RecommendationNotFoundError(
                    f"Recomendacao {review_input.recommendation_id} nao encontrada."
                )

            recommendation.review(
                status=review_input.status,
                comment=review_input.comment,
                reviewed_by=review_input.reviewed_by,
            )
            await uow.recommendation_repository.update_review(recommendation)
            await uow.commit()

        return to_recommendation_view(recommendation)
