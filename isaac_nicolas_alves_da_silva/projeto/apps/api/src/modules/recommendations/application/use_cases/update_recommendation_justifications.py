"""Caso de uso para atualizar a justificativa de recomendacoes existentes."""

from uuid import UUID

from apps.api.src.modules.recommendations.application.public.recommendation_justification_updater import (
    RecommendationJustificationUpdater,
)
from apps.api.src.modules.recommendations.application.unit_of_work import (
    RecommendationsUnitOfWorkFactory,
)


class UpdateRecommendationJustifications(RecommendationJustificationUpdater):
    """Casa recomendacoes existentes por ``technology_slug`` e atualiza a
    justificativa, sem tocar score/keywords/evidence_ids."""

    def __init__(self, uow_factory: RecommendationsUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def update_justifications(
        self, startup_id: UUID, justifications: dict[str, str]
    ) -> None:
        async with self._uow_factory() as uow:
            existing = await uow.recommendation_repository.list_by_startup_id(
                startup_id
            )
            for recommendation in existing:
                new_justification = justifications.get(recommendation.technology_slug)
                if new_justification is None:
                    continue
                recommendation.update_justification(new_justification)
                await uow.recommendation_repository.update_justification(
                    recommendation.id, recommendation.justification
                )
            await uow.commit()
