from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
from uuid import uuid4

from requests import RequestException

from app.briefing import generate_briefing_markdown, validate_evidence
from app.config import Settings
from app.pipeline import PipelineStep, PipelineTrace, SequentialStateGraph, create_state_graph
from app.profile_extraction import (
    extract_structured_profile,
    structured_profile_search_text,
)
from app.rag.embeddings import EmbeddingProvider
from app.rag.ingest import ingest_startup_evidence_pages
from app.rag.vector_store import QdrantHttpClient
from app.schemas.analysis import (
    StartupAnalysisRequest,
    StartupAnalysisResponse,
    StartupRecommendation,
    StartupSearchPlan,
    StartupSourceSummary,
    StartupStructuredProfile,
)
from app.scraping import crawl_public_website_text, fetch_public_source_evidence
from app.startup_sources import resolve_startup_by_name
from app.storage import DatabaseUnavailable, save_analysis_run


ScoreStartupProfile = Callable[[str, int], tuple[str, int, int, int]]
RerankRecommendationResults = Callable[
    [list[dict[str, object]], str, Settings | None],
    list[dict[str, object]],
]
StartupCandidateLoader = Callable[[Settings], list[dict[str, object]]]
NvidiaFreshnessRunner = Callable[..., Any]


LOW_COMPLEXITY_CATEGORIES = {
    "model_deployment",
    "ai_enterprise",
    "speech_ai",
    "customer_service",
}

HIGH_COMPLEXITY_CATEGORIES = {
    "infrastructure",
    "simulation",
    "robotics",
    "digital_twins",
    "optimization",
}


def recommendation_implementation_complexity(category: str, priority: str) -> str:
    normalized_category = category.lower().strip()
    if normalized_category in HIGH_COMPLEXITY_CATEGORIES:
        return "high"
    if normalized_category in LOW_COMPLEXITY_CATEGORIES and priority == "high":
        return "low"
    return "medium"


def recommendation_next_action(
    *,
    technology: str,
    category: str,
    priority: str,
) -> str:
    normalized_category = category.lower().strip()
    if normalized_category == "model_deployment":
        return (
            f"Mapear um modelo ou endpoint critico e testar {technology} em um "
            "piloto curto de latencia, custo e observabilidade."
        )
    if normalized_category in {"data_processing", "data_science"}:
        return (
            f"Selecionar um pipeline de dados pesado e estimar ganho de tempo com "
            f"{technology} antes de propor migracao maior."
        )
    if normalized_category == "optimization":
        return (
            f"Separar um problema real de roteirizacao, scheduling ou alocacao e "
            f"validar {technology} com uma amostra operacional."
        )
    if normalized_category in {"speech_ai", "conversational_ai"}:
        return (
            f"Escolher um fluxo de voz ou atendimento e medir qualidade, latencia "
            f"e custo usando {technology}."
        )
    if priority == "high":
        return (
            f"Agendar uma conversa tecnica de 30 minutos para validar aderencia de "
            f"{technology} ao principal gargalo da startup."
        )
    return (
        f"Manter {technology} como opcao de aprofundamento apos confirmar os gaps "
        "tecnicos com a equipe da startup."
    )


def compute_analysis_quality_metrics(state: AnalysisGraphState) -> dict[str, object]:
    public_pages = [
        page
        for page in state.source_pages
        if int(page.get("characters") or 0) >= 120 and page.get("source_url")
    ]
    recommendation_checks = [
        check for check in state.evidence_checks if check.claim_type == "recommendation"
    ]
    grounded_recommendations = [
        check
        for check in recommendation_checks
        if not check.blocks_recommendation
        and any("nvidia" in str(url).lower() for url in check.source_urls)
        and len(check.evidence_ids) >= 2
    ]
    actionable_recommendations = [
        recommendation for recommendation in state.recommendations if recommendation.next_action
    ]
    trace_steps = state.trace.as_list()
    pipeline_latency_ms = sum(
        int(step.get("duration_ms") or 0)
        for step in trace_steps
        if step.get("duration_ms") is not None
    )
    total_recommendations = len(state.recommendations)
    groundedness_percent = (
        round(len(grounded_recommendations) / total_recommendations * 100, 1)
        if total_recommendations
        else 0.0
    )
    actionable_percent = (
        round(len(actionable_recommendations) / total_recommendations * 100, 1)
        if total_recommendations
        else 0.0
    )
    evidence_coverage_percent = round(min(100.0, len(public_pages) / 3 * 100), 1)

    return {
        "public_source_pages": len(public_pages),
        "evidence_coverage_percent": evidence_coverage_percent,
        "grounded_recommendations": len(grounded_recommendations),
        "recommendation_groundedness_percent": groundedness_percent,
        "actionable_recommendation_percent": actionable_percent,
        "pipeline_latency_ms": pipeline_latency_ms,
        "blocked_evidence_checks": sum(
            1 for check in state.evidence_checks if check.blocks_recommendation
        ),
        "targets": {
            "at_least_2_public_sources": len(public_pages) >= 2,
            "groundedness_at_least_90_percent": groundedness_percent >= 90.0
            or total_recommendations == 0,
            "all_recommendations_actionable": actionable_percent == 100.0
            or total_recommendations == 0,
            "briefing_under_5_minutes": pipeline_latency_ms < 300000,
        },
    }


def build_startup_search_plan(
    request: StartupAnalysisRequest,
    *,
    resolved_candidate: dict[str, object] | None,
) -> StartupSearchPlan:
    source_priorities = [
        "startup_catalog",
        "official_website" if request.website_url else "official_website_candidate",
        "public_news_sources",
        "nvidia_knowledge_base",
        "startup_evidence_vector_store",
    ]
    if resolved_candidate:
        source_priorities.insert(1, "resolved_catalog_candidate")

    query_parts = [
        request.startup_name,
        request.sector or "",
        request.description or "",
        " ".join(request.technical_gaps),
    ]
    query = " ".join(part for part in query_parts if part).strip()
    raw_terms = [
        request.startup_name,
        request.sector or "",
        *request.technical_gaps,
        "inteligencia artificial",
        "machine learning",
        "clientes",
        "funding",
        "tecnologia",
    ]
    search_terms: list[str] = []
    seen_terms: set[str] = set()
    for term in raw_terms:
        clean_term = " ".join(str(term or "").split()).strip()
        key = clean_term.lower()
        if not clean_term or key in seen_terms:
            continue
        seen_terms.add(key)
        search_terms.append(clean_term)

    return StartupSearchPlan(
        query=query or request.startup_name,
        search_terms=search_terms[:12],
        source_priorities=source_priorities,
        evidence_targets=[
            "produto",
            "sinais_de_ia",
            "founders",
            "funding",
            "clientes",
            "tecnologias",
            "gaps_tecnicos",
        ],
    )


@dataclass
class AnalysisGraphState:
    request: StartupAnalysisRequest
    settings: Settings
    vector_store: QdrantHttpClient
    embedder: EmbeddingProvider
    startup_candidate_loader: StartupCandidateLoader
    nvidia_freshness_runner: NvidiaFreshnessRunner
    score_startup_profile: ScoreStartupProfile
    rerank_recommendation_results: RerankRecommendationResults
    trace: PipelineTrace = field(default_factory=PipelineTrace)
    current_step: PipelineStep | None = None

    startup_candidates: list[dict[str, object]] = field(default_factory=list)
    resolved_candidate: dict[str, object] | None = None
    effective_request: StartupAnalysisRequest | None = None
    search_plan: StartupSearchPlan | None = None
    source_summary: StartupSourceSummary | None = None
    source_pages: list[dict[str, object]] = field(default_factory=list)
    collected_website_text: str = ""
    structured_profile: StartupStructuredProfile = field(
        default_factory=StartupStructuredProfile
    )
    profile_text: str = ""
    rag_results: list[dict[str, object]] = field(default_factory=list)
    recommendations: list[StartupRecommendation] = field(default_factory=list)
    classification: str = "insufficient_evidence"
    ai_native_score: int = 0
    wrapper_risk_score: int = 0
    nvidia_fit_score: int = 0
    evidence_checks: list[Any] = field(default_factory=list)
    quality_metrics: dict[str, object] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    briefing_markdown: str = ""
    analysis_run_id: str | None = None
    planned_analysis_run_id: str = field(default_factory=lambda: str(uuid4()))
    startup_evidence_chunks: int = 0

    @property
    def step(self) -> PipelineStep:
        if self.current_step is None:
            raise RuntimeError("No active pipeline step.")
        return self.current_step


class SearchPlannerAgent:
    def __call__(self, state: AnalysisGraphState) -> None:
        request = state.request
        state.startup_candidates = state.startup_candidate_loader(state.settings)
        state.resolved_candidate = resolve_startup_by_name(
            state.startup_candidates,
            request.startup_name,
        )

        effective_startup_name = request.startup_name
        effective_website_url = request.website_url
        effective_sector = request.sector
        effective_description = request.description

        state.limitations.append(
            f"Embeddings ativos: {state.settings.embedding_provider}. "
            "A qualidade depende da base ingerida e das fontes publicas disponiveis."
        )

        if state.resolved_candidate:
            effective_startup_name = str(
                state.resolved_candidate.get("startup_name") or request.startup_name
            )
            effective_website_url = (
                effective_website_url or state.resolved_candidate.get("website_url")
            )
            effective_sector = effective_sector or str(
                state.resolved_candidate.get("sector") or ""
            )
            candidate_description = str(
                state.resolved_candidate.get("description") or ""
            ).strip()
            if not effective_description and candidate_description:
                effective_description = candidate_description
            elif effective_description and candidate_description:
                effective_description = (
                    f"{effective_description}\n\n"
                    f"Fonte de startups: {candidate_description}"
                )
            state.limitations.append(
                "Startup resolvida automaticamente pela fonte configurada "
                f"({state.resolved_candidate.get('source', 'unknown')})."
            )

        state.effective_request = StartupAnalysisRequest(
            startup_name=effective_startup_name,
            website_url=effective_website_url,
            sector=effective_sector,
            description=effective_description,
            technical_gaps=request.technical_gaps,
            force_nvidia_update_check=request.force_nvidia_update_check,
        )
        state.search_plan = build_startup_search_plan(
            state.effective_request,
            resolved_candidate=state.resolved_candidate,
        )

        state.step.finish(
            summary=(
                "Startup resolvida pela fonte configurada."
                if state.resolved_candidate
                else "Startup nao resolvida automaticamente; usando entrada manual."
            ),
            metadata={
                "candidates_loaded": len(state.startup_candidates),
                "resolved": bool(state.resolved_candidate),
                "source": (
                    state.resolved_candidate.get("source")
                    if state.resolved_candidate
                    else None
                ),
                "effective_startup_name": state.effective_request.startup_name,
                "search_plan_version": state.search_plan.version,
                "search_terms": state.search_plan.search_terms,
                "source_priorities": state.search_plan.source_priorities,
                "evidence_targets": state.search_plan.evidence_targets,
            },
        )


class KnowledgeFreshnessAgent:
    def __call__(self, state: AnalysisGraphState) -> None:
        freshness = state.nvidia_freshness_runner(
            state.settings,
            max_sources=max(1, min(state.settings.nvidia_freshness_max_sources, 24)),
            max_chars_per_source=12000,
            persist_results=True,
            reingest_changed=True,
            vector_store=state.vector_store,
            embedder=state.embedder,
        )
        state.limitations.append(
            "Freshness NVIDIA: "
            f"{freshness.checked} fonte(s) checada(s), "
            f"{freshness.changed} nova(s)/alterada(s), "
            f"{freshness.failed} falha(s), "
            f"{freshness.reingested} reingerida(s)."
        )
        state.step.finish(
            summary="Freshness NVIDIA checado antes da analise.",
            metadata={
                "checked": freshness.checked,
                "changed": freshness.changed,
                "failed": freshness.failed,
                "persisted": freshness.persisted,
                "reingested": freshness.reingested,
            },
        )


class ScraperAgent:
    def _extra_public_source_urls(self, state: AnalysisGraphState) -> list[tuple[str, str]]:
        if not state.resolved_candidate:
            return []
        sources: list[tuple[str, str]] = []
        for field_name, source_type in (
            ("source_url", "catalog_or_news_source"),
            ("github_url", "github_repository"),
        ):
            value = str(state.resolved_candidate.get(field_name) or "").strip()
            if value.startswith(("http://", "https://")):
                sources.append((value, source_type))
        return sources

    def _append_extra_public_sources(self, state: AnalysisGraphState) -> int:
        seen_urls = {
            str(page.get("source_url") or "").rstrip("/")
            for page in state.source_pages
            if page.get("source_url")
        }
        added = 0
        for source_url, source_type in self._extra_public_source_urls(state):
            if source_url.rstrip("/") in seen_urls:
                continue
            try:
                page = fetch_public_source_evidence(
                    source_url,
                    source_type=source_type,
                    max_chars=4500,
                )
            except RequestException:
                continue
            if int(page.get("characters") or 0) < 120:
                continue
            seen_urls.add(str(page.get("source_url") or source_url).rstrip("/"))
            state.source_pages.append(page)
            added += 1
            if not state.source_summary:
                state.source_summary = StartupSourceSummary(
                    source_url=page["source_url"],
                    status="collected",
                    characters=int(page.get("characters") or 0),
                    excerpt=str(page.get("excerpt") or "")[:480],
                )
        return added

    def _refresh_collected_text(self, state: AnalysisGraphState) -> None:
        state.collected_website_text = "\n\n".join(
            f"Fonte: {page.get('source_url')}\n{page.get('text') or page.get('excerpt') or ''}"
            for page in state.source_pages
        )

    def __call__(self, state: AnalysisGraphState) -> None:
        effective_request = require_effective_request(state)
        if not effective_request.website_url:
            extra_sources = self._append_extra_public_sources(state)
            if extra_sources:
                self._refresh_collected_text(state)
                state.limitations.append(
                    "Startup sem site oficial confirmado; a analise usou "
                    f"{extra_sources} fonte(s) publica(s) alternativa(s) do catalogo."
                )
                state.step.finish(
                    summary="Fontes publicas alternativas coletadas.",
                    metadata={
                        "website_url": None,
                        "pages": len(state.source_pages),
                        "extra_public_sources": extra_sources,
                    },
                )
                return
            state.limitations.append(
                "Startup nao encontrada na fonte configurada com site publico ou fonte "
                "publica alternativa; a analise usou os dados manuais disponiveis."
            )
            state.step.finish(
                status="skipped",
                summary="Nenhum site publico disponivel; analise usa dados manuais.",
            )
            return

        try:
            collected = crawl_public_website_text(
                str(effective_request.website_url),
                require_brazilian_startup=not bool(state.resolved_candidate),
            )
        except RequestException as error:
            extra_sources = self._append_extra_public_sources(state)
            if extra_sources:
                self._refresh_collected_text(state)
                state.limitations.append(
                    "Nao foi possivel coletar o site informado; a analise usou "
                    f"{extra_sources} fonte(s) publica(s) alternativa(s)."
                )
                state.step.finish(
                    summary="Site falhou, mas fontes publicas alternativas foram coletadas.",
                    metadata={
                        "website_url": str(effective_request.website_url),
                        "pages": len(state.source_pages),
                        "extra_public_sources": extra_sources,
                        "primary_error": str(error),
                    },
                )
                return
            state.source_summary = StartupSourceSummary(
                source_url=str(effective_request.website_url),
                status="failed",
                characters=0,
                excerpt=str(error),
            )
            state.limitations.append(
                "Nao foi possivel coletar o site informado; a analise usou os dados manuais."
            )
            state.step.finish(
                status="failed",
                summary="Falha ao coletar o site publico.",
                metadata={
                    "website_url": str(effective_request.website_url),
                    "error": str(error),
                },
            )
            return

        state.collected_website_text = str(collected["text"])
        state.source_pages = list(collected.get("pages", []))
        extra_sources = self._append_extra_public_sources(state)
        if extra_sources:
            self._refresh_collected_text(state)
        state.source_summary = StartupSourceSummary(
            source_url=collected["source_url"],
            status="collected",
            characters=sum(int(page.get("characters") or 0) for page in state.source_pages),
            excerpt=state.collected_website_text[:480],
        )
        state.limitations.append(
            f"Scraping coletou {len(state.source_pages)} pagina(s), incluindo "
            f"{extra_sources} fonte(s) publica(s) complementar(es), "
            "priorizando links internos de produto, tecnologia, docs e casos."
        )
        state.step.finish(
            summary="Site publico coletado com mini-crawler.",
            metadata={
                "website_url": str(effective_request.website_url),
                "pages": len(state.source_pages),
                "characters": collected["characters"],
                "extra_public_sources": extra_sources,
            },
        )


class ExtractorAgent:
    def __call__(self, state: AnalysisGraphState) -> None:
        effective_request = require_effective_request(state)
        state.structured_profile = extract_structured_profile(
            description=effective_request.description,
            source_pages=state.source_pages,
        )
        structured_profile_text = structured_profile_search_text(
            state.structured_profile
        )
        profile_parts = [
            effective_request.startup_name,
            effective_request.sector or "",
            effective_request.description or "",
            state.collected_website_text,
            structured_profile_text,
            " ".join(effective_request.technical_gaps),
        ]
        state.profile_text = " ".join(part for part in profile_parts if part).strip()
        extracted_counts = {
            "founders": len(state.structured_profile.founders),
            "funding": len(state.structured_profile.funding),
            "customers": len(state.structured_profile.customers),
            "technologies": len(state.structured_profile.technologies),
            "ai_signals": len(state.structured_profile.ai_signals),
        }
        if any(extracted_counts.values()):
            state.limitations.append(
                "Extractor Agent montou perfil estruturado com "
                + ", ".join(
                    f"{field_name}={count}"
                    for field_name, count in extracted_counts.items()
                    if count
                )
                + "."
            )
        state.step.finish(
            summary="Perfil textual e estruturado consolidado para classificacao e RAG.",
            metadata={
                "profile_characters": len(state.profile_text),
                "technical_gaps": len(effective_request.technical_gaps),
                "has_scraped_text": bool(state.collected_website_text),
                "structured_profile": extracted_counts,
            },
        )


class NvidiaRagAgent:
    def __call__(self, state: AnalysisGraphState) -> None:
        state.rag_results = state.vector_store.search(
            collection_name=state.settings.nvidia_collection,
            vector=state.embedder.embed(state.profile_text),
            limit=12,
        )
        state.step.finish(
            summary="Busca vetorial executada na base NVIDIA.",
            metadata={
                "raw_results": len(state.rag_results),
                "collection": state.settings.nvidia_collection,
            },
        )


class RecommendationAgent:
    def __call__(self, state: AnalysisGraphState) -> None:
        recommendations: list[StartupRecommendation] = []
        seen_products: set[str] = set()
        for result in state.rerank_recommendation_results(
            state.rag_results,
            state.profile_text,
            state.settings,
        ):
            if len(recommendations) >= 5:
                break
            payload = result.get("payload") or {}
            product_name = payload.get("product_name", "Unknown")
            if product_name in seen_products:
                continue
            seen_products.add(str(product_name))
            category = str(payload.get("category", "unknown"))
            priority = "high" if len(recommendations) < 2 else "medium"
            complexity = recommendation_implementation_complexity(category, priority)

            recommendations.append(
                StartupRecommendation(
                    technology=str(product_name),
                    category=category,
                    priority=priority,
                    implementation_complexity=complexity,
                    next_action=recommendation_next_action(
                        technology=str(product_name),
                        category=category,
                        priority=priority,
                    ),
                    technical_reason=str(payload.get("chunk_text", "")),
                    business_reason=(
                        "Pode reduzir risco tecnico e acelerar a evolucao de um "
                        "produto de IA para operacao em producao."
                    ),
                    source_url=payload.get("source_url", ""),
                    retrieval_score=float(
                        result.get("rerank_score", result.get("score", 0.0))
                    ),
                    rerank_details=result.get("rerank_details") or {},
                )
            )

        state.recommendations = recommendations
        if not state.recommendations:
            state.limitations.append(
                "Nenhuma recomendacao encontrada; ingira a base NVIDIA seed primeiro."
            )
        state.step.finish(
            summary="Resultados NVIDIA reranqueados e convertidos em recomendacoes.",
            metadata={
                "recommendations": len(state.recommendations),
                "reranker_provider": state.settings.reranker_provider,
                "technologies": [
                    recommendation.technology for recommendation in state.recommendations
                ],
            },
        )


class StartupClassifierAgent:
    def __call__(self, state: AnalysisGraphState) -> None:
        (
            state.classification,
            state.ai_native_score,
            state.wrapper_risk_score,
            state.nvidia_fit_score,
        ) = state.score_startup_profile(state.profile_text, len(state.recommendations))
        state.step.finish(
            summary="Scores AI-native, wrapper risk e NVIDIA fit calculados.",
            metadata={
                "classification": state.classification,
                "ai_native_score": state.ai_native_score,
                "wrapper_risk_score": state.wrapper_risk_score,
                "nvidia_fit_score": state.nvidia_fit_score,
            },
        )


class EvidenceValidatorAgent:
    def __call__(self, state: AnalysisGraphState) -> None:
        effective_request = require_effective_request(state)
        min_recommendation_retrieval_score = (
            0.15
            if state.settings.embedding_provider.strip().lower() == "hash"
            else 0.35
        )
        state.evidence_checks = validate_evidence(
            description=effective_request.description,
            source_summary=state.source_summary,
            structured_profile=state.structured_profile,
            gaps=effective_request.technical_gaps,
            recommendations=state.recommendations,
            source_pages=state.source_pages,
            min_recommendation_retrieval_score=min_recommendation_retrieval_score,
            analysis_run_id=state.planned_analysis_run_id,
        )
        blocked_checks = [
            check for check in state.evidence_checks if check.blocks_recommendation
        ]
        blocked_recommendation_technologies = {
            check.recommendation_technology
            for check in blocked_checks
            if check.claim_type == "recommendation" and check.recommendation_technology
        }
        if blocked_recommendation_technologies:
            before_count = len(state.recommendations)
            state.recommendations = [
                recommendation
                for recommendation in state.recommendations
                if recommendation.technology not in blocked_recommendation_technologies
            ]
            removed_count = before_count - len(state.recommendations)
            state.limitations.append(
                "Evidence Validator bloqueou "
                f"{removed_count} recomendacao(oes) sem lastro minimo: "
                f"{', '.join(sorted(blocked_recommendation_technologies))}."
            )
        if blocked_checks:
            state.limitations.append(
                "Evidence Validator marcou "
                f"{len(blocked_checks)} ponto(s) como insuficientes para decisao forte."
            )
        state.step.finish(
            summary="Evidencias e confianca avaliadas.",
            metadata={
                "checks": len(state.evidence_checks),
                "blocked_checks": len(blocked_checks),
                "blocked_recommendations": sorted(
                    blocked_recommendation_technologies
                ),
                "remaining_recommendations": len(state.recommendations),
            },
        )


class BriefingAgent:
    def __call__(self, state: AnalysisGraphState) -> None:
        effective_request = require_effective_request(state)
        state.quality_metrics = compute_analysis_quality_metrics(state)
        state.briefing_markdown = generate_briefing_markdown(
            startup_name=effective_request.startup_name,
            sector=effective_request.sector,
            classification=state.classification,
            ai_native_score=state.ai_native_score,
            wrapper_risk_score=state.wrapper_risk_score,
            nvidia_fit_score=state.nvidia_fit_score,
            source_summary=state.source_summary,
            gaps=effective_request.technical_gaps,
            recommendations=state.recommendations,
            evidence_checks=state.evidence_checks,
            limitations=state.limitations,
            search_plan=state.search_plan,
            structured_profile=state.structured_profile,
            quality_metrics=state.quality_metrics,
            pipeline_trace=state.trace.as_list(),
        )
        state.step.finish(
            summary="Briefing Markdown gerado.",
            metadata={"characters": len(state.briefing_markdown)},
        )


class StorageAgent:
    def __call__(self, state: AnalysisGraphState) -> None:
        effective_request = require_effective_request(state)
        try:
            state.analysis_run_id = save_analysis_run(
                settings=state.settings,
                request=effective_request,
                classification=state.classification,
                ai_native_score=state.ai_native_score,
                wrapper_risk_score=state.wrapper_risk_score,
                nvidia_fit_score=state.nvidia_fit_score,
                source_pages=state.source_pages,
                detected_gaps=effective_request.technical_gaps,
                recommendations=state.recommendations,
                evidence_checks=state.evidence_checks,
                briefing_markdown=state.briefing_markdown,
                limitations=state.limitations,
                analysis_run_id=state.planned_analysis_run_id,
            )
            state.step.finish(
                summary="Analise salva no Postgres.",
                metadata={"analysis_run_id": state.analysis_run_id},
            )
        except DatabaseUnavailable as error:
            state.limitations.append(f"Historico Postgres nao salvo: {error}")
            state.step.finish(
                status="skipped",
                summary="Historico Postgres nao salvo.",
                metadata={"error": str(error)},
            )
        except Exception as error:
            state.limitations.append(f"Historico Postgres nao salvo: {error}")
            state.step.finish(
                status="failed",
                summary="Falha ao salvar historico Postgres.",
                metadata={"error": str(error)},
            )


class StartupEvidenceAgent:
    def __call__(self, state: AnalysisGraphState) -> None:
        effective_request = require_effective_request(state)
        if state.analysis_run_id and state.source_pages:
            try:
                evidence_ingestion = ingest_startup_evidence_pages(
                    vector_store=state.vector_store,
                    embedder=state.embedder,
                    collection_name=state.settings.startup_collection,
                    startup_name=effective_request.startup_name,
                    analysis_run_id=state.analysis_run_id,
                    pages=state.source_pages,
                    website_url=(
                        str(effective_request.website_url)
                        if effective_request.website_url
                        else None
                    ),
                )
                state.startup_evidence_chunks = int(evidence_ingestion["chunks"])
                state.step.finish(
                    summary="Evidencias da startup salvas no Qdrant.",
                    metadata={
                        "chunks": state.startup_evidence_chunks,
                        "pages": len(state.source_pages),
                    },
                )
            except RequestException as error:
                state.limitations.append(
                    f"Evidencias da startup nao salvas no Qdrant: {error}"
                )
                state.step.finish(
                    status="failed",
                    summary="Falha ao salvar evidencias da startup no Qdrant.",
                    metadata={"error": str(error)},
                )
        elif state.source_pages and not state.analysis_run_id:
            state.limitations.append(
                "Evidencias da startup nao foram salvas no Qdrant porque a analise "
                "nao recebeu um analysis_run_id do Postgres."
            )
            state.step.finish(
                status="skipped",
                summary="Evidencias nao salvas por falta de analysis_run_id.",
                metadata={"pages": len(state.source_pages)},
            )
        else:
            state.step.finish(
                status="skipped",
                summary="Nenhuma evidencia de site publico para salvar no Qdrant.",
            )


def require_effective_request(state: AnalysisGraphState) -> StartupAnalysisRequest:
    if state.effective_request is None:
        raise RuntimeError("Effective request was not initialized by Search Planner Agent.")
    return state.effective_request


def should_check_freshness(state: AnalysisGraphState) -> bool:
    return state.request.force_nvidia_update_check


def build_analysis_graph(trace: PipelineTrace) -> SequentialStateGraph:
    graph = create_state_graph(trace)
    graph.add_node("startup_resolution", "Search Planner Agent", SearchPlannerAgent())
    graph.add_node(
        "nvidia_freshness_check",
        "Knowledge Freshness Agent",
        KnowledgeFreshnessAgent(),
        condition=should_check_freshness,
    )
    graph.add_node(
        "startup_scraping",
        "Scraper Agent",
        ScraperAgent(),
        retry_exceptions=(RequestException,),
        retries=1,
    )
    graph.add_node("profile_extraction", "Extractor Agent", ExtractorAgent())
    graph.add_node(
        "nvidia_rag_retrieval",
        "NVIDIA RAG Agent",
        NvidiaRagAgent(),
        retry_exceptions=(RequestException,),
        retries=1,
    )
    graph.add_node(
        "recommendation_reranking",
        "Recommendation Agent",
        RecommendationAgent(),
    )
    graph.add_node(
        "startup_classification",
        "Startup Classifier Agent",
        StartupClassifierAgent(),
    )
    graph.add_node(
        "evidence_validation",
        "Evidence Validator Agent",
        EvidenceValidatorAgent(),
    )
    graph.add_node("briefing_generation", "Briefing Agent", BriefingAgent())
    graph.add_node("analysis_persistence", "Storage Agent", StorageAgent())
    graph.add_node(
        "startup_evidence_ingestion",
        "Startup Evidence Agent",
        StartupEvidenceAgent(),
        retry_exceptions=(RequestException,),
        retries=1,
    )
    return graph


def run_startup_analysis_graph(
    *,
    request: StartupAnalysisRequest,
    settings: Settings,
    vector_store: QdrantHttpClient,
    embedder: EmbeddingProvider,
    startup_candidate_loader: StartupCandidateLoader,
    nvidia_freshness_runner: NvidiaFreshnessRunner,
    score_startup_profile: ScoreStartupProfile,
    rerank_recommendation_results: RerankRecommendationResults,
) -> StartupAnalysisResponse:
    trace = PipelineTrace()
    state = AnalysisGraphState(
        request=request,
        settings=settings,
        vector_store=vector_store,
        embedder=embedder,
        startup_candidate_loader=startup_candidate_loader,
        nvidia_freshness_runner=nvidia_freshness_runner,
        score_startup_profile=score_startup_profile,
        rerank_recommendation_results=rerank_recommendation_results,
        trace=trace,
    )
    graph = build_analysis_graph(trace)
    graph.run(state)
    effective_request = require_effective_request(state)

    return StartupAnalysisResponse(
        analysis_run_id=state.analysis_run_id,
        startup_name=effective_request.startup_name,
        classification=state.classification,
        ai_native_score=state.ai_native_score,
        wrapper_risk_score=state.wrapper_risk_score,
        nvidia_fit_score=state.nvidia_fit_score,
        search_plan=state.search_plan,
        source_summary=state.source_summary,
        source_pages=state.source_pages,
        structured_profile=state.structured_profile,
        startup_evidence_chunks=state.startup_evidence_chunks,
        detected_gaps=effective_request.technical_gaps,
        recommendations=state.recommendations,
        evidence_checks=state.evidence_checks,
        briefing_markdown=state.briefing_markdown,
        quality_metrics=state.quality_metrics,
        limitations=state.limitations,
        pipeline_trace=trace.as_list(),
    )
