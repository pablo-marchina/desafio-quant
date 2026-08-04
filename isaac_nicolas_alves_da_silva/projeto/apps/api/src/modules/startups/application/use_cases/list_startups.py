"""Caso de uso para o historico paginado de startups."""

from apps.api.src.modules.startups.application.dto import (
    ListStartupsInput,
    StartupPageView,
)
from apps.api.src.modules.startups.application.unit_of_work import (
    StartupsUnitOfWorkFactory,
)
from apps.api.src.modules.startups.application.use_cases.create_startup import (
    to_startup_view,
)


class ListStartups:
    """Lista startups para navegacao, com filtros do portfolio."""

    def __init__(self, uow_factory: StartupsUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, list_input: ListStartupsInput) -> StartupPageView:
        async with self._uow_factory() as uow:
            startups, total = await uow.startup_repository.list_page(
                page=list_input.page,
                page_size=list_input.page_size,
                query=list_input.query,
                sector=list_input.sector,
                country=list_input.country,
                ai_maturity_level=list_input.ai_maturity_level,
            )
        return StartupPageView(
            items=[to_startup_view(startup) for startup in startups],
            total=total,
            page=list_input.page,
            page_size=list_input.page_size,
        )
