"""Caso de uso para criar startup."""

from uuid import UUID

from apps.api.src.modules.startups.application.dto import (
    CreateStartupInput,
    StartupAIProfileView,
    StartupView,
)
from apps.api.src.modules.startups.application.public.startup_creator import (
    StartupCreator,
)
from apps.api.src.modules.startups.application.unit_of_work import (
    StartupsUnitOfWorkFactory,
)
from apps.api.src.modules.startups.domain.entities import Startup
from apps.api.src.modules.startups.domain.policies import (
    find_duplicate_startup,
    infer_country_from_url,
)


class CreateStartup(StartupCreator):
    """Cria uma startup no repositorio relacional.

    Antes de criar, checa se uma startup existente provavelmente e' a
    mesma empresa (mesmo dominio, ou nome muito similar -
    `domain/policies.py::find_duplicate_startup`). Se achar, devolve o
    registro existente em vez de criar um duplicado - quem chama
    (`orchestration`) so usa o id devolvido pra anexar evidencia, e' o
    mesmo comportamento independente de ter criado ou reaproveitado.
    """

    def __init__(self, uow_factory: StartupsUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def create_startup(
        self, *, name: str, website_url: str | None = None
    ) -> UUID:
        view = await self.execute(
            CreateStartupInput(name=name, website_url=website_url)
        )
        return view.id

    async def execute(self, startup_input: CreateStartupInput) -> StartupView:
        async with self._uow_factory() as uow:
            existing = await uow.startup_repository.list_all()
            duplicate = find_duplicate_startup(
                name=startup_input.name,
                website_url=startup_input.website_url,
                existing=existing,
            )
            if duplicate is not None:
                return to_startup_view(duplicate)

            startup = Startup(
                name=startup_input.name,
                website_url=startup_input.website_url,
                description=startup_input.description,
                sector=startup_input.sector,
                country=startup_input.country
                or infer_country_from_url(startup_input.website_url),
            )
            await uow.startup_repository.save(startup)
            await uow.commit()

        return to_startup_view(startup)


def to_startup_view(startup: Startup) -> StartupView:
    ai_profile_view = None
    if startup.ai_profile is not None:
        p = startup.ai_profile
        ai_profile_view = StartupAIProfileView(
            ai_workload_type=p.ai_workload_type.value,
            model_type=p.model_type.value,
            data_modality=p.data_modality.value,
            deployment_stage=p.deployment_stage.value,
            infra_environment=p.infra_environment.value,
            gpu_need=p.gpu_need.value,
            latency_requirement=p.latency_requirement.value,
            scale_signal=p.scale_signal,
            current_tools=list(p.current_tools),
            business_goal=p.business_goal,
            field_confidence=dict(p.field_confidence),
            field_evidence_ids=dict(p.field_evidence_ids),
            extracted_at=p.extracted_at,
        )
    return StartupView(
        id=startup.id,
        name=startup.name,
        website_url=startup.website_url,
        description=startup.description,
        sector=startup.sector,
        country=startup.country,
        ai_maturity_level=startup.ai_maturity_level,
        classification_reason=startup.classification_reason,
        classified_at=startup.classified_at,
        founders=list(startup.founders),
        funding_stage=startup.funding_stage,
        funding_amount_usd=startup.funding_amount_usd,
        customers=list(startup.customers),
        created_at=startup.created_at,
        updated_at=startup.updated_at,
        ai_profile=ai_profile_view,
        field_confidence=dict(startup.field_confidence),
        field_evidence_ids=dict(startup.field_evidence_ids),
    )
