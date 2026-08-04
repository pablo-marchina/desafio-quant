"""Caso de uso para listar evidencias de uma startup."""

from uuid import UUID

from apps.api.src.modules.startups.application.dto import StartupEvidenceView
from apps.api.src.modules.startups.application.unit_of_work import (
    StartupsUnitOfWorkFactory,
)
from apps.api.src.modules.startups.application.use_cases.add_startup_evidence import (
    to_evidence_view,
)
from apps.api.src.modules.startups.domain.exceptions import StartupNotFoundError


class ListStartupEvidences:
    """Lista evidencias associadas a uma startup."""

    def __init__(self, uow_factory: StartupsUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, *, startup_id: UUID) -> list[StartupEvidenceView]:
        async with self._uow_factory() as uow:
            startup = await uow.startup_repository.get_by_id(startup_id)
            if startup is None:
                raise StartupNotFoundError(f"Startup {startup_id} nao encontrada.")
            evidences = await uow.evidence_repository.list_by_startup_id(startup_id)

        return [to_evidence_view(evidence) for evidence in evidences]
