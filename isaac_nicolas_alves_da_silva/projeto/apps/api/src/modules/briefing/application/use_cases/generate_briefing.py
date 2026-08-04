"""Caso de uso para gerar o briefing executivo de uma startup."""

import asyncio
from uuid import UUID

from apps.api.src.modules.briefing.application.dto import (
    BriefingView,
    GenerateBriefingInput,
)
from apps.api.src.modules.briefing.application.ports import (
    NvidiaContextGrounder,
    RecommendationsSource,
    StartupProfileSource,
)
from apps.api.src.modules.briefing.application.public.briefing_generator import (
    BriefingGenerator,
)
from apps.api.src.modules.briefing.application.unit_of_work import (
    BriefingsUnitOfWorkFactory,
)
from apps.api.src.modules.briefing.domain.entities import Briefing
from apps.api.src.modules.briefing.domain.policies import (
    EvidenceItem,
    RecommendationItem,
    StartupAIProfileItem,
    StartupSummary,
    assess_risks,
    build_briefing_markdown,
    suggest_next_actions,
)
from apps.api.src.shared.logging import get_logger


logger = get_logger(__name__)
NVIDIA_CONTEXT_TIMEOUT_SECONDS = 30


class GenerateBriefing(BriefingGenerator):
    """Monta e persiste o briefing executivo mais recente de uma startup.

    Cada chamada substitui o briefing anterior da mesma startup - V1 nao
    versiona geracoes, apenas mantem o resultado mais recente (mesma decisao
    de ``GenerateRecommendations``).
    """

    def __init__(
        self,
        uow_factory: BriefingsUnitOfWorkFactory,
        profile_source: StartupProfileSource,
        recommendations_source: RecommendationsSource,
        grounder: NvidiaContextGrounder | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._profile_source = profile_source
        self._recommendations_source = recommendations_source
        self._grounder = grounder

    async def generate(self, startup_id: UUID) -> BriefingView:
        profile = await self._profile_source.get_profile(startup_id)
        recommendation_snapshots = await self._recommendations_source.list_by_startup(
            startup_id
        )

        startup = StartupSummary(
            name=profile.startup.name,
            sector=profile.startup.sector,
            description=profile.startup.description,
            country=profile.startup.country,
            website_url=profile.startup.website_url,
        )
        evidences = [
            EvidenceItem(
                title=evidence.title,
                source_url=evidence.source_url,
                evidence_type=evidence.evidence_type,
                confidence_score=evidence.confidence_score,
            )
            for evidence in profile.evidences
        ]
        recommendations = [
            RecommendationItem(
                technology_name=recommendation.technology_name,
                category=recommendation.category,
                score=recommendation.score,
                justification=recommendation.justification,
                confidence=recommendation.confidence,
                complexity=recommendation.complexity,
                nivel=recommendation.nivel,
                faltando=recommendation.faltando,
                signal_origins=recommendation.signal_origins,
                missing_signals=recommendation.missing_signals,
            )
            for recommendation in recommendation_snapshots
        ]
        ai_profile = (
            StartupAIProfileItem(
                ai_workload_type=profile.ai_profile.ai_workload_type,
                model_type=profile.ai_profile.model_type,
                data_modality=profile.ai_profile.data_modality,
                deployment_stage=profile.ai_profile.deployment_stage,
                infra_environment=profile.ai_profile.infra_environment,
                gpu_need=profile.ai_profile.gpu_need,
                latency_requirement=profile.ai_profile.latency_requirement,
                scale_signal=profile.ai_profile.scale_signal,
                current_tools=profile.ai_profile.current_tools,
                business_goal=profile.ai_profile.business_goal,
                field_confidence=profile.ai_profile.field_confidence,
                field_evidence_ids=profile.ai_profile.field_evidence_ids,
            )
            if profile.ai_profile is not None
            else None
        )

        nvidia_context = await self._ground_context(startup.sector, recommendations)

        risks = assess_risks(evidences, recommendations)
        next_actions = suggest_next_actions(recommendations)
        content = build_briefing_markdown(
            startup=startup,
            evidences=evidences,
            recommendations=recommendations,
            risks=risks,
            next_actions=next_actions,
            ai_profile=ai_profile,
            nvidia_context=nvidia_context,
        )

        briefing = Briefing(startup_id=startup_id, content=content)

        async with self._uow_factory() as uow:
            await uow.briefing_repository.delete_by_startup_id(startup_id)
            await uow.briefing_repository.save(briefing)
            await uow.commit()

        return to_briefing_view(briefing)

    async def execute(self, briefing_input: GenerateBriefingInput) -> BriefingView:
        return await self.generate(briefing_input.startup_id)

    async def _ground_context(
        self, sector: str | None, recommendations: list[RecommendationItem]
    ) -> str | None:
        """Sintese de setor via RAG, best-effort (1 chamada, nao por tecnologia).

        Sem grounder configurado ou sem recomendacao nenhuma (nada pra
        sintetizar), pula a chamada de rede inteiramente.
        """

        if self._grounder is None or not recommendations:
            return None

        technology_names = tuple(r.technology_name for r in recommendations)
        try:
            grounded = await asyncio.wait_for(
                self._grounder.ground(sector, technology_names),
                timeout=NVIDIA_CONTEXT_TIMEOUT_SECONDS,
            )
        except Exception as error:
            logger.warning(
                "nvidia context grounding skipped after best-effort failure",
                extra={"reason": str(error)},
            )
            return None

        if grounded is None:
            return None

        # Link Markdown (`[Fonte N](url)`), nao URL puro - rastreabilidade
        # ponta a ponta (P3) exige que isso vire link clicavel no frontend,
        # que renderiza `content` como Markdown de verdade.
        sources = ", ".join(
            f"[Fonte {index}]({url})"
            for index, url in enumerate(grounded.citation_urls, start=1)
        )
        return f"{grounded.text} Fontes: {sources}."


def to_briefing_view(briefing: Briefing) -> BriefingView:
    return BriefingView(
        id=briefing.id,
        startup_id=briefing.startup_id,
        content=briefing.content,
        review_status=briefing.review_status,
        review_comment=briefing.review_comment,
        reviewed_by=briefing.reviewed_by,
        reviewed_at=briefing.reviewed_at,
        generated_at=briefing.generated_at,
    )
