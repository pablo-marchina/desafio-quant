"""Caso de uso para buscar um briefing por id."""

from uuid import UUID

from apps.api.src.modules.briefing.application.dto import BriefingView
from apps.api.src.modules.briefing.application.unit_of_work import (
    BriefingsUnitOfWorkFactory,
)
from apps.api.src.modules.briefing.application.use_cases.generate_briefing import (
    to_briefing_view,
)
from apps.api.src.modules.briefing.domain.exceptions import BriefingNotFoundError


class GetBriefing:
    """Busca um briefing por id."""

    def __init__(self, uow_factory: BriefingsUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, *, briefing_id: UUID) -> BriefingView:
        async with self._uow_factory() as uow:
            briefing = await uow.briefing_repository.get_by_id(briefing_id)

        if briefing is None:
            raise BriefingNotFoundError(f"Briefing {briefing_id} nao encontrado.")

        return to_briefing_view(briefing)
