"""Caso de uso para atualizar startup."""

from apps.api.src.modules.startups.application.dto import (
    StartupView,
    UpdateStartupInput,
)
from apps.api.src.modules.startups.application.unit_of_work import (
    StartupsUnitOfWorkFactory,
)
from apps.api.src.modules.startups.application.use_cases.create_startup import (
    to_startup_view,
)
from apps.api.src.modules.startups.domain.exceptions import StartupNotFoundError


class UpdateStartup:
    """Atualiza campos basicos de uma startup."""

    def __init__(self, uow_factory: StartupsUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, startup_input: UpdateStartupInput) -> StartupView:
        async with self._uow_factory() as uow:
            startup = await uow.startup_repository.get_by_id(
                startup_input.startup_id
            )
            if startup is None:
                raise StartupNotFoundError(
                    f"Startup {startup_input.startup_id} nao encontrada."
                )

            startup.update(
                name=startup_input.name,
                website_url=startup_input.website_url,
                description=startup_input.description,
                sector=startup_input.sector,
                country=startup_input.country,
                founders=startup_input.founders,
                funding_stage=startup_input.funding_stage,
                funding_amount_usd=startup_input.funding_amount_usd,
                customers=startup_input.customers,
            )
            await uow.startup_repository.save(startup)
            await uow.commit()

        return to_startup_view(startup)
