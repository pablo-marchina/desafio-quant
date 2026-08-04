"""Adaptador que liga briefing ao contrato publico do modulo startups.

Esta e a UNICA peca do modulo ``briefing`` que conhece o modulo ``startups``
— e mesmo assim, conhece apenas o contrato publico
(``startups/application/public/startup_profile_reader.py``). A traducao do
``StartupNotFoundError`` (vocabulario de startups) para
``StartupProfileUnavailableError`` (vocabulario de briefing) acontece
somente aqui.
"""

from uuid import UUID

from apps.api.src.modules.briefing.application.dto import (
    EvidenceSnapshot,
    StartupAIProfileSnapshot,
    StartupProfileSnapshot,
    StartupSnapshot,
)
from apps.api.src.modules.briefing.application.ports import StartupProfileSource
from apps.api.src.modules.briefing.domain.exceptions import (
    StartupProfileUnavailableError,
)
from apps.api.src.modules.startups.application.public.startup_profile_reader import (
    StartupProfileReader,
)
from apps.api.src.modules.startups.domain.exceptions import StartupNotFoundError


class StartupsModuleProfileSource(StartupProfileSource):
    """Implementa ``StartupProfileSource`` chamando o modulo startups."""

    def __init__(self, reader: StartupProfileReader) -> None:
        self._reader = reader

    async def get_profile(self, startup_id: UUID) -> StartupProfileSnapshot:
        try:
            profile = await self._reader.get_profile(startup_id)
        except StartupNotFoundError as error:
            raise StartupProfileUnavailableError(str(error)) from error

        ai_profile = None
        if profile.startup.ai_profile is not None:
            source_profile = profile.startup.ai_profile
            ai_profile = StartupAIProfileSnapshot(
                ai_workload_type=source_profile.ai_workload_type,
                model_type=source_profile.model_type,
                data_modality=source_profile.data_modality,
                deployment_stage=source_profile.deployment_stage,
                infra_environment=source_profile.infra_environment,
                gpu_need=source_profile.gpu_need,
                latency_requirement=source_profile.latency_requirement,
                scale_signal=source_profile.scale_signal,
                current_tools=tuple(source_profile.current_tools),
                business_goal=source_profile.business_goal,
                field_confidence=dict(source_profile.field_confidence),
                field_evidence_ids=dict(source_profile.field_evidence_ids),
            )

        return StartupProfileSnapshot(
            startup=StartupSnapshot(
                name=profile.startup.name,
                sector=profile.startup.sector,
                description=profile.startup.description,
                country=profile.startup.country,
                website_url=profile.startup.website_url,
            ),
            evidences=tuple(
                EvidenceSnapshot(
                    title=evidence.title,
                    source_url=evidence.source_url,
                    evidence_type=evidence.evidence_type.value,
                    confidence_score=evidence.confidence_score,
                )
                for evidence in profile.evidences
            ),
            ai_profile=ai_profile,
        )
