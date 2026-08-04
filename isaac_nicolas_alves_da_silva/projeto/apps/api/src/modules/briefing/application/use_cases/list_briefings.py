"""Caso de uso para listar briefings de uma startup."""

from uuid import UUID

from apps.api.src.modules.briefing.application.dto import BriefingView
from apps.api.src.modules.briefing.application.unit_of_work import (
    BriefingsUnitOfWorkFactory,
)
from apps.api.src.modules.briefing.application.use_cases.generate_briefing import (
    to_briefing_view,
)


class ListBriefings:
    """Lista briefings associados a uma startup."""

    def __init__(self, uow_factory: BriefingsUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, *, startup_id: UUID) -> list[BriefingView]:
        async with self._uow_factory() as uow:
            briefings = await uow.briefing_repository.list_by_startup_id(startup_id)

        return [to_briefing_view(briefing) for briefing in briefings]
