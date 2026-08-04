"""Caso de uso para buscar startup."""

from uuid import UUID

from apps.api.src.modules.startups.application.dto import StartupView
from apps.api.src.modules.startups.application.unit_of_work import (
    StartupsUnitOfWorkFactory,
)
from apps.api.src.modules.startups.application.use_cases.create_startup import (
    to_startup_view,
)
from apps.api.src.modules.startups.domain.exceptions import StartupNotFoundError


class GetStartup:
    """Busca uma startup por id."""

    def __init__(self, uow_factory: StartupsUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, *, startup_id: UUID) -> StartupView:
        async with self._uow_factory() as uow:
            startup = await uow.startup_repository.get_by_id(startup_id)

        if startup is None:
            raise StartupNotFoundError(f"Startup {startup_id} nao encontrada.")

        return to_startup_view(startup)
