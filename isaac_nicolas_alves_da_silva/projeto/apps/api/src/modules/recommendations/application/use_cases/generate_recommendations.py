"""Caso de uso para gerar recomendacoes NVIDIA para uma startup."""

import asyncio
from uuid import UUID

from apps.api.src.modules.recommendations.application.dto import (
    GenerateRecommendationsInput,
    GroundedJustification,
    RecommendationView,
    StartupProfileSnapshot,
)
from apps.api.src.modules.recommendations.application.ports import (
    NvidiaCatalogSource,
    NvidiaKnowledgeGrounder,
    NvidiaSemanticCandidateSelector,
    StartupProfileSource,
)
from apps.api.src.modules.recommendations.application.public.recommendation_generator import (
    RecommendationGenerator,
)
from apps.api.src.modules.recommendations.application.unit_of_work import (
    RecommendationsUnitOfWorkFactory,
)
from apps.api.src.modules.recommendations.domain.entities import Recommendation
from apps.api.src.modules.recommendations.domain.policies import (
    EvidenceSignal,
    MatchResult,
    StartupAIContext,
    TechnologyCandidate,
    match_technologies,
)

INCEPTION_SLUG = "nvidia-inception"

# Sinais textuais que indicam uma SEGUNDA carga de IA além da principal.
# Resolve o caso Driva/Econodata: ai_workload_type="analytics" perde o
# copiloto/agente (NLP). Aqui detectamos workloads adicionais no texto.
_SECONDARY_WORKLOAD_SIGNALS = {
    "nlp": ("copilot", "copiloto", "chatbot", "agente", "agent", "llm",
            "linguagem natural", "assistente", "geração de texto", "generative"),
    "vision": ("visão computacional", "computer vision", "imagem", "vídeo", "ocr"),
    "speech": ("voz", "fala", "transcrição", "speech", "asr", "tts"),
}


def _detect_secondary_workloads(text: str) -> tuple[str, ...]:
    t = text.lower()
    return tuple(
        wl for wl, terms in _SECONDARY_WORKLOAD_SIGNALS.items()
        if any(term in t for term in terms)
    )


class GenerateRecommendations(RecommendationGenerator):
    """Cruza o perfil da startup com o catalogo NVIDIA e persiste o resultado.

    Cada chamada substitui as recomendacoes anteriores da mesma startup -
    V1 nao versiona geracoes, apenas mantem o resultado mais recente.
    """

    def __init__(
        self,
        uow_factory: RecommendationsUnitOfWorkFactory,
        profile_source: StartupProfileSource,
        catalog_source: NvidiaCatalogSource,
        grounder: NvidiaKnowledgeGrounder | None = None,
        semantic_selector: NvidiaSemanticCandidateSelector | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._profile_source = profile_source
        self._catalog_source = catalog_source
        self._grounder = grounder
        self._semantic_selector = semantic_selector

    async def generate(self, startup_id: UUID) -> list[RecommendationView]:
        profile = await self._profile_source.get_profile(startup_id)
        technologies = await self._catalog_source.list_technologies()

        evidence_signals = [
            EvidenceSignal(
                evidence_id=evidence.evidence_id,
                text=f"{evidence.title or ''} {evidence.notes or ''}".lower(),
                confidence_score=evidence.confidence_score,
                source_url=evidence.source_url,
                evidence_type=evidence.evidence_type,
            )
            for evidence in profile.evidences
        ]
        candidates = [
            TechnologyCandidate(
                slug=technology.slug,
                name=technology.name,
                category=technology.category,
                use_cases=technology.use_cases,
                keywords=technology.keywords,
                complexity=technology.complexity,
                supported_workloads=dict(technology.supported_workloads),
            )
            for technology in technologies
        ]

        candidates = await self._apply_semantic_prefilter(candidates, profile)

        ai_context: StartupAIContext | None = None
        if profile.ai_profile is not None:
            p = profile.ai_profile
            ai_context = StartupAIContext(
                ai_workload_type=p.ai_workload_type,
                deployment_stage=p.deployment_stage,
                gpu_need=p.gpu_need,
                has_operational_signal=p.has_operational_signal,
                profile_strength=p.profile_strength,
                secondary_workloads=_detect_secondary_workloads(
                    f"{profile.sector or ''} {profile.description or ''} "
                    + " ".join(s.text for s in evidence_signals)
                ),
            )

        matches = match_technologies(
            sector=profile.sector,
            description=profile.description,
            ai_maturity_level=profile.ai_maturity_level,
            ai_context=ai_context,
            evidence_signals=evidence_signals,
            technologies=candidates,
        )

        if not matches:
            floor = self._inception_floor(startup_id, candidates)
            if floor is not None:
                matches = [floor]

        grounded_results = await self._ground_matches(matches)
        recommendations = [
            self._to_recommendation(startup_id, match, grounded)
            for match, grounded in zip(matches, grounded_results, strict=True)
        ]

        async with self._uow_factory() as uow:
            await uow.recommendation_repository.delete_by_startup_id(startup_id)
            for recommendation in recommendations:
                await uow.recommendation_repository.save(recommendation)
            await uow.commit()

        return [
            to_recommendation_view(recommendation, priority=rank)
            for rank, recommendation in enumerate(recommendations, start=1)
        ]

    async def execute(
        self, recommendation_input: GenerateRecommendationsInput
    ) -> list[RecommendationView]:
        return await self.generate(recommendation_input.startup_id)

    async def _apply_semantic_prefilter(
        self,
        candidates: list[TechnologyCandidate],
        profile: StartupProfileSnapshot,
    ) -> list[TechnologyCandidate]:
        """Pre-filtra candidatos via retrieval semantico no nvidia_knowledge.

        Constroi uma query combinando setor + descricao + textos de evidencia
        da startup e consulta o Qdrant para identificar quais tecnologias do
        catalogo aparecem no conteudo recuperado.

        Fallback (retorna todos): sem selector, query vazia, ou nenhum slug
        identificado (nvidia_knowledge nao indexado ou conteudo insuficiente).
        """
        if self._semantic_selector is None:
            return candidates

        parts = [profile.sector or "", profile.description or ""]
        if profile.ai_profile is not None:
            parts += [
                profile.ai_profile.ai_workload_type,
                profile.ai_profile.deployment_stage,
                profile.ai_profile.gpu_need,
            ]
        parts += [
            f"{e.title or ''} {e.notes or ''}".strip()
            for e in profile.evidences
        ]
        query = " ".join(p for p in parts if p)
        if not query.strip():
            return candidates

        tech_keywords = {c.slug: c.keywords for c in candidates}
        semantic_slugs = await self._semantic_selector.select(query, tech_keywords)

        if not semantic_slugs:
            return candidates

        return [c for c in candidates if c.slug in semantic_slugs]

    async def _ground_matches(
        self, matches: list[MatchResult]
    ) -> list[GroundedJustification | None]:
        """Busca fundamentacao real em paralelo, 1 chamada RAG por match.

        Best-effort: sem grounder configurado, devolve `None` pra cada match
        sem nenhuma chamada de rede.
        """

        if self._grounder is None or not matches:
            return [None] * len(matches)

        return await asyncio.gather(
            *(
                self._grounder.ground(match.technology.name, _use_case(match))
                for match in matches
            )
        )

    @staticmethod
    def _inception_floor(
        startup_id: UUID,
        candidates: list[TechnologyCandidate],
    ) -> MatchResult | None:
        """Retorna um MatchResult minimo para NVIDIA Inception quando matches e vazio.

        O floor garante que nenhum briefing seja completamente vazio — Inception e
        o ponto de entrada natural no ecossistema NVIDIA para qualquer startup de IA.
        Score 0.21 (acima do MIN_MATCH_SCORE=0.20), nivel exploratoria, confianca
        muito baixa (sem evidencia concreta de fit).
        """
        inception = next(
            (c for c in candidates if c.slug == INCEPTION_SLUG), None
        )
        if inception is None:
            return None

        from apps.api.src.modules.recommendations.domain.policies import (
            NIVEL_EXPLORATORIA,
        )

        return MatchResult(
            technology=inception,
            score=0.21,
            confidence=0.10,
            matched_keywords=(),
            evidence_ids=(),
            signal_origins=(),
            missing_signals=inception.keywords,
            score_breakdown={
                "workload_alignment": 0.40,
                "evidence_signal": 0.20,
                "startup_maturity": 0.50,
                "keyword_prior": 0.0,
                "implementation_viability": 0.60,
            },
            nivel=NIVEL_EXPLORATORIA,
            faltando=("evidências concretas sobre uso da tecnologia",),
        )

    @staticmethod
    def _to_recommendation(
        startup_id: UUID,
        match: MatchResult,
        grounded: GroundedJustification | None,
    ) -> Recommendation:
        return Recommendation(
            startup_id=startup_id,
            technology_slug=match.technology.slug,
            technology_name=match.technology.name,
            category=match.technology.category,
            score=match.score,
            confidence=match.confidence,
            complexity=match.technology.complexity,
            justification=(
                _build_grounded_justification(grounded)
                if grounded is not None
                else _build_justification(match)
            ),
            matched_keywords=match.matched_keywords,
            evidence_ids=match.evidence_ids,
            signal_origins=match.signal_origins,
            missing_signals=match.missing_signals,
            nivel=match.nivel,
            faltando=match.faltando,
        )


def _use_case(match: MatchResult) -> str:
    return match.technology.use_cases[0] if match.technology.use_cases else (
        match.technology.name
    )


def _build_justification(match: MatchResult) -> str:
    if not match.matched_keywords:
        if match.technology.slug != INCEPTION_SLUG:
            origins = ", ".join(match.signal_origins) or "perfil estruturado de IA"
            return (
                f"O perfil estruturado indica alinhamento com {match.technology.name} "
                f"({origins}), mas ainda faltam keywords literais ou evidencias "
                "tecnicas diretas. Tratar como hipotese a qualificar antes de "
                "propor implementacao."
            )
        return (
            f"{match.technology.name} e o ponto de entrada natural no ecossistema NVIDIA "
            "para startups de IA. Nao foram identificados sinais especificos de fit "
            "com o perfil atual — recomenda-se aprofundar a coleta de evidencias."
        )
    keywords = ", ".join(match.matched_keywords)
    return (
        f"Evidencias e perfil mencionam: {keywords}. "
        f"{match.technology.name} e indicada para: {_use_case(match)}."
    )


def _build_grounded_justification(grounded: GroundedJustification) -> str:
    """Citacoes como link Markdown (`[Fonte N](url)`), nao URL puro.

    Necessario pra rastreabilidade ponta a ponta (P3): o frontend renderiza
    `justification` como Markdown de verdade desde o fechamento dessa
    decisao - URL puro nao virava link clicavel sem essa sintaxe.
    """

    sources = ", ".join(
        f"[Fonte {index}]({url})"
        for index, url in enumerate(grounded.citation_urls, start=1)
    )
    return f"{grounded.text} Fontes: {sources}."


def to_recommendation_view(recommendation: Recommendation, *, priority: int = 1) -> RecommendationView:
    return RecommendationView(
        id=recommendation.id,
        startup_id=recommendation.startup_id,
        technology_slug=recommendation.technology_slug,
        technology_name=recommendation.technology_name,
        category=recommendation.category,
        score=recommendation.score,
        confidence=recommendation.confidence,
        complexity=recommendation.complexity,
        priority=priority,
        justification=recommendation.justification,
        matched_keywords=list(recommendation.matched_keywords),
        evidence_ids=list(recommendation.evidence_ids),
        signal_origins=list(recommendation.signal_origins),
        missing_signals=list(recommendation.missing_signals),
        nivel=recommendation.nivel,
        faltando=list(recommendation.faltando),
        review_status=recommendation.review_status,
        review_comment=recommendation.review_comment,
        reviewed_by=recommendation.reviewed_by,
        reviewed_at=recommendation.reviewed_at,
        created_at=recommendation.created_at,
    )
