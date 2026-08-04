"""Caso de uso que implementa o contrato publico StartupProfileReader."""

from uuid import UUID

from apps.api.src.modules.startups.application.dto import StartupProfileView
from apps.api.src.modules.startups.application.public.startup_profile_reader import (
    StartupProfileReader,
)
from apps.api.src.modules.startups.application.unit_of_work import (
    StartupsUnitOfWorkFactory,
)
from apps.api.src.modules.startups.application.use_cases.add_startup_evidence import (
    to_evidence_view,
)
from apps.api.src.modules.startups.application.use_cases.create_startup import (
    to_startup_view,
)
from apps.api.src.modules.startups.domain.exceptions import StartupNotFoundError


class GetStartupProfile(StartupProfileReader):
    """Busca a startup e suas evidencias para consumo de outros modulos."""

    def __init__(self, uow_factory: StartupsUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def get_profile(self, startup_id: UUID) -> StartupProfileView:
        async with self._uow_factory() as uow:
            startup = await uow.startup_repository.get_by_id(startup_id)
            if startup is None:
                raise StartupNotFoundError(f"Startup {startup_id} nao encontrada.")
            evidences = await uow.evidence_repository.list_by_startup_id(startup_id)

        return StartupProfileView(
            startup=to_startup_view(startup),
            evidences=[to_evidence_view(evidence) for evidence in evidences],
        )
