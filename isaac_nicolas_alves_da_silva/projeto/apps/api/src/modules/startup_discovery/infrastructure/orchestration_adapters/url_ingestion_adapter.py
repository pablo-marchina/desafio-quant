"""Adapter que submete URLs descobertas ao pipeline de orchestration."""

from uuid import UUID

from apps.api.src.modules.orchestration.application.dto import (
    CreateUrlIngestionJobInput,
)
from apps.api.src.modules.orchestration.application.use_cases.create_url_ingestion_job import (
    CreateUrlIngestionJob,
)
from apps.api.src.modules.startups.application.unit_of_work import (
    StartupsUnitOfWorkFactory,
)
from apps.api.src.modules.startups.domain.policies import find_duplicate_startup


class StartupDiscoveryUrlIngestionAdapter:
    """Submete uma URL de startup descoberta como url_ingestion_job.

    source_type = "startup_evidence" para que o pipeline de analise
    (ANALYZING) seja ativado ao fim do embedding, exatamente como uma
    URL submetida manualmente pelo usuario.
    """

    def __init__(
        self,
        use_case: CreateUrlIngestionJob,
        startups_uow_factory: StartupsUnitOfWorkFactory | None = None,
    ) -> None:
        self._use_case = use_case
        self._startups_uow_factory = startups_uow_factory

    async def submit(self, url: str, *, name: str | None = None) -> UUID:
        startup_id = await self._resolve_existing_startup_id(url, name=name)
        view = await self._use_case.execute(
            CreateUrlIngestionJobInput(
                url=url,
                source_type="startup_evidence",
                startup_id=startup_id,
            )
        )
        return view.id

    async def _resolve_existing_startup_id(
        self,
        url: str,
        *,
        name: str | None,
    ) -> UUID | None:
        if self._startups_uow_factory is None:
            return None

        async with self._startups_uow_factory() as uow:
            existing = await uow.startup_repository.list_all()

        duplicate = find_duplicate_startup(
            name=name or url,
            website_url=url,
            existing=existing,
        )
        return duplicate.id if duplicate is not None else None
