"""Adaptador que liga orchestration aos contratos publicos do modulo startups.

Esta e a UNICA peca do modulo ``orchestration`` que conhece o modulo
``startups`` — e mesmo assim, conhece apenas os 4 contratos publicos
(``startups/application/public/``). O swallow da indisponibilidade de
extract/classify (sem ``GEMINI_API_KEY``) acontece dentro de ``startups``
(``try_extract``/``try_classify`` ja sao best-effort no contrato), nao
aqui.
"""

from uuid import UUID

from apps.api.src.modules.orchestration.application.ports import (
    StartupExtractionAttempt,
    StartupProfileSnapshot,
    StartupsPort,
)
from apps.api.src.modules.startups.application.public.classification_trigger import (
    ClassificationTrigger,
)
from apps.api.src.modules.startups.application.public.evidence_attacher import (
    EvidenceAttacher,
)
from apps.api.src.modules.startups.application.public.extraction_trigger import (
    ExtractionTrigger,
)
from apps.api.src.modules.startups.application.public.startup_creator import (
    StartupCreator,
)
from apps.api.src.modules.startups.application.public.startup_profile_reader import (
    StartupProfileReader,
)


class StartupsModulePort(StartupsPort):
    """Implementa ``StartupsPort`` chamando o modulo startups."""

    def __init__(
        self,
        creator: StartupCreator,
        evidence_attacher: EvidenceAttacher,
        extraction_trigger: ExtractionTrigger,
        classification_trigger: ClassificationTrigger,
        profile_reader: StartupProfileReader,
    ) -> None:
        self._creator = creator
        self._evidence_attacher = evidence_attacher
        self._extraction_trigger = extraction_trigger
        self._classification_trigger = classification_trigger
        self._profile_reader = profile_reader

    async def create_startup(self, *, name: str, website_url: str) -> UUID:
        return await self._creator.create_startup(name=name, website_url=website_url)

    async def attach_evidence(
        self,
        *,
        startup_id: UUID,
        scraping_result_id: UUID,
        source_url: str,
        title: str | None,
        notes: str | None,
    ) -> None:
        await self._evidence_attacher.attach_evidence(
            startup_id=startup_id,
            scraping_result_id=scraping_result_id,
            source_url=source_url,
            title=title,
            notes=notes,
        )

    async def try_extract(self, startup_id: UUID) -> StartupExtractionAttempt:
        result = await self._extraction_trigger.try_extract(startup_id)
        return StartupExtractionAttempt(
            succeeded=result.succeeded,
            unavailable=result.unavailable,
            timed_out=result.timed_out,
            error_message=result.error_message,
        )

    async def try_classify(self, startup_id: UUID) -> None:
        await self._classification_trigger.try_classify(startup_id)

    async def get_profile(self, startup_id: UUID) -> StartupProfileSnapshot:
        profile = await self._profile_reader.get_profile(startup_id)
        startup = profile.startup
        ai_workload_type = "unknown"
        deployment_stage = "unknown"
        gpu_need = "unknown"
        if startup.ai_profile is not None:
            ai_workload_type = startup.ai_profile.ai_workload_type or "unknown"
            deployment_stage = (
                getattr(startup.ai_profile.deployment_stage, "value", None)
                or startup.ai_profile.deployment_stage
                or "unknown"
            )
            gpu_need = (
                getattr(startup.ai_profile.gpu_need, "value", None)
                or startup.ai_profile.gpu_need
                or "unknown"
            )

        return StartupProfileSnapshot(
            name=startup.name,
            website_url=startup.website_url,
            founders=list(startup.founders),
            funding_stage=startup.funding_stage.value
            if startup.funding_stage is not None
            else None,
            customers=list(startup.customers),
            evidence_urls=[evidence.source_url for evidence in profile.evidences],
            ai_workload_type=ai_workload_type,
            deployment_stage=deployment_stage,
            gpu_need=gpu_need,
        )
