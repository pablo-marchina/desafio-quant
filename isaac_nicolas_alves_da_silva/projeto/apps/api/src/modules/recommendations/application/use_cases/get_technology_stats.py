"""Caso de uso para estatisticas das tecnologias NVIDIA mais recomendadas."""

from apps.api.src.modules.recommendations.application.dto import (
    TechnologyStatView,
    TechnologyStatsView,
)
from apps.api.src.modules.recommendations.application.unit_of_work import (
    RecommendationsUnitOfWorkFactory,
)


class GetTechnologyStats:

    def __init__(self, uow_factory: RecommendationsUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, *, limit: int = 10) -> TechnologyStatsView:
        async with self._uow_factory() as uow:
            rows = await uow.recommendation_repository.count_by_technology(limit=limit)

        return TechnologyStatsView(
            items=[
                TechnologyStatView(
                    technology_slug=slug,
                    technology_name=name,
                    count=count,
                )
                for slug, name, count in rows
            ]
        )
