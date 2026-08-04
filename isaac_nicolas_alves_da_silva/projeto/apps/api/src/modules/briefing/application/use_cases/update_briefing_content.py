"""Caso de uso para atualizar o conteudo do briefing mais recente de uma startup."""

from uuid import UUID

from apps.api.src.modules.briefing.application.public.briefing_content_updater import (
    BriefingContentUpdater,
)
from apps.api.src.modules.briefing.application.unit_of_work import (
    BriefingsUnitOfWorkFactory,
)
from apps.api.src.modules.briefing.domain.exceptions import BriefingNotFoundError


class UpdateBriefingContent(BriefingContentUpdater):
    """Atualiza o conteudo do briefing mais recente, sem remontar secoes."""

    def __init__(self, uow_factory: BriefingsUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def update_content(self, startup_id: UUID, content: str) -> UUID:
        async with self._uow_factory() as uow:
            existing = await uow.briefing_repository.list_by_startup_id(startup_id)
            if not existing:
                raise BriefingNotFoundError(
                    f"Nenhum briefing encontrado para a startup {startup_id}."
                )

            briefing = existing[0]
            briefing.update_content(content)
            await uow.briefing_repository.update_content(
                briefing.id, briefing.content
            )
            await uow.commit()
            return briefing.id
