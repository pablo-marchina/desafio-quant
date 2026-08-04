"""Caso de uso para estatisticas de distribuicao do portfolio."""

from apps.api.src.modules.startups.application.dto import MaturityDistributionView
from apps.api.src.modules.startups.application.unit_of_work import (
    StartupsUnitOfWorkFactory,
)


class GetPortfolioStats:

    def __init__(self, uow_factory: StartupsUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self) -> MaturityDistributionView:
        async with self._uow_factory() as uow:
            counts = await uow.startup_repository.count_by_maturity()

        ai_native = counts.get("ai_native", 0)
        ai_enabled = counts.get("ai_enabled", 0)
        non_ai = counts.get("non_ai", 0)
        unclassified = counts.get("unclassified", 0)

        return MaturityDistributionView(
            ai_native=ai_native,
            ai_enabled=ai_enabled,
            non_ai=non_ai,
            unclassified=unclassified,
            total=ai_native + ai_enabled + non_ai + unclassified,
        )
