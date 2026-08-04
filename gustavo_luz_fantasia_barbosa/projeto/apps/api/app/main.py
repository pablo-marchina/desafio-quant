import hmac
import logging
import re
import unicodedata
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from requests import RequestException

from app.analysis_graph import run_startup_analysis_graph
from app.briefing_export import build_pdf
from app.config import Settings, get_settings
from app.rag.embeddings import EmbeddingProvider, create_embedding_provider
from app.rag.freshness import check_nvidia_sources
from app.rag.ingest import (
    ingest_nvidia_official_pages,
    ingest_nvidia_seed_documents,
)
from app.rag.reranker import (
    recommendation_boost as enhanced_recommendation_boost,
    rerank_results,
)
from app.pipeline import graph_engine_status
from app.rag.seed_data import NVIDIA_TECHNOLOGY_DOCS
from app.rag.vector_store import QdrantHttpClient
from app.scraping import BrazilianStartupValidationError
from app.schemas.analysis import (
    AnalysisBriefingResponse,
    AnalysisRunSummary,
    StartupAnalysisRequest,
    StartupAnalysisResponse,
)
from app.schemas.radar import (
    StartupRadarRequest,
    StartupRadarResponse,
    StartupRadarResult,
    StartupRepertoireRefreshRequest,
    StartupRepertoireRefreshResponse,
    StartupRepertoireEnrichRequest,
    StartupRepertoireEnrichResponse,
    StartupRepertoireReviewRequest,
    StartupRepertoireReviewResponse,
    StartupRepertoireResponse,
    StartupRepertoireUseRequest,
    StartupRepertoireUseResponse,
    StartupDiscoveryResult,
    StartupSearchRequest,
    StartupSearchResponse,
    StartupSearchResult,
    StartupRadarToolFit,
)
from app.schemas.rag import (
    IngestNvidiaRequest,
    IngestNvidiaOfficialRequest,
    IngestNvidiaOfficialResponse,
    IngestNvidiaResponse,
    NvidiaFreshnessCheckRequest,
    NvidiaFreshnessCheckResponse,
    RagSearchRequest,
    RagSearchResponse,
    RagSearchResult,
    StartupEvidenceSearchRequest,
    StartupEvidenceSearchResponse,
    StartupEvidenceSearchResult,
    TechnologySummary,
)
from app.storage import (
    DatabaseUnavailable,
    catalog_status,
    database_health,
    database_enabled,
    ensure_database_schema,
    get_analysis_briefing,
    list_startup_catalog,
    list_startup_discoveries,
    list_analysis_runs,
    list_nvidia_document_snapshots,
    promote_startup_discoveries_to_catalog,
    record_nvidia_document_versions,
    save_nvidia_update_checks,
    seed_startup_catalog_from_csv,
    startup_key,
    sync_nvidia_source_registry,
    upsert_startup_catalog,
    upsert_startup_discoveries,
)
from app.startups.source_metadata import (
    build_startup_source_evidence,
    startup_source_confidence,
    startup_source_summary,
)
from app.startup_discovery import (
    collect_discoveries_from_sources,
    discovery_key,
    enrich_discoveries,
    parse_discovery_source_urls,
    read_discoveries,
    refresh_discovery_repertoire,
    review_discovery_with_website,
    use_discovered_startups,
    write_discoveries,
)
from app.startup_sources import (
    load_startup_candidates,
    search_startup_candidates,
    startup_source_status,
)


logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).resolve().parent / "static"


def configured_cors_origins(settings: Settings) -> list[str]:
    origins = [
        origin.strip()
        for origin in settings.cors_allow_origins.split(",")
        if origin.strip()
    ]
    return origins or ["http://127.0.0.1:8000", "http://localhost:8000"]


def initialize_runtime() -> None:
    settings = get_settings()
    try:
        ensure_database_schema(settings)
        seed_startup_catalog_from_csv(settings)
        sync_nvidia_source_registry(settings, NVIDIA_TECHNOLOGY_DOCS)
    except DatabaseUnavailable as error:
        logger.info("Postgres initialization skipped: %s", error)
    except Exception:
        logger.exception("Runtime initialization failed.")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize_runtime()
    yield


def require_admin_access(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> None:
    expected_token = (settings.admin_api_token or "").strip()
    if not expected_token:
        return

    provided_token = (request.headers.get("x-admin-token") or "").strip()
    authorization = (request.headers.get("authorization") or "").strip()
    if authorization.lower().startswith("bearer "):
        provided_token = authorization[7:].strip()

    if not hmac.compare_digest(provided_token, expected_token):
        raise HTTPException(
            status_code=401,
            detail="Token administrativo ausente ou invalido.",
        )


app = FastAPI(
    title="Seraphim Scout API",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_cors_origins(get_settings()),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


def get_vector_store(settings: Settings = Depends(get_settings)) -> QdrantHttpClient:
    return QdrantHttpClient(
        base_url=settings.qdrant_url,
        vector_size=settings.vector_size,
        distance=settings.vector_distance,
    )


def get_embedder(settings: Settings = Depends(get_settings)) -> EmbeddingProvider:
    try:
        return create_embedding_provider(settings)
    except ValueError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


def get_active_startup_candidates(settings: Settings) -> list[dict[str, object]]:
    if database_enabled(settings):
        try:
            candidates = list_startup_catalog(settings)
            if candidates:
                return candidates
        except DatabaseUnavailable as error:
            logger.info("Startup catalog fallback to CSV: %s", error)
    return load_startup_candidates(settings.startup_source_path)


def get_startup_catalog_source(settings: Settings) -> dict[str, object]:
    status = catalog_status(settings)
    if status.get("backend") == "postgres" and status.get("status") == "ok":
        return {
            "source": "postgres",
            "source_path": "startup_catalog",
            "status": status,
        }
    fallback = startup_source_status(settings.startup_source_path)
    return {
        "source": str(fallback["source"]),
        "source_path": str(fallback["path"]),
        "status": status,
    }


def configured_discovery_sources(settings: Settings) -> list[str]:
    return parse_discovery_source_urls(
        settings.startup_discovery_source_urls,
        settings.startup_discovery_source_url,
    )


def catalog_source_from_discovery(discovery: dict[str, object], prefix: str) -> str:
    source = str(discovery.get("source") or "news").replace("_news", "")
    source = source.strip("_") or "news"
    return f"{prefix}_{source}"


def catalog_candidate_from_discovery(
    discovery: dict[str, object],
    *,
    source_prefix: str,
) -> dict[str, object]:
    return {
        "startup_name": discovery["startup_name"],
        "country_code": discovery.get("country_code") or "BR",
        "sector": discovery.get("sector") or "unknown",
        "stage": discovery.get("stage"),
        "source": catalog_source_from_discovery(discovery, source_prefix),
        "website_url": discovery.get("website_url"),
        "github_url": discovery.get("github_url"),
        "source_url": discovery.get("article_url") or discovery.get("source_url"),
        "description": discovery.get("description") or discovery.get("article_title"),
        "signals": discovery.get("signals") or ["noticia", "Brasil"],
    }


def nvidia_freshness_summary(
    checks: list[dict[str, object]],
    *,
    persisted: bool = False,
    reingested: int = 0,
) -> NvidiaFreshnessCheckResponse:
    changed_statuses = {"new", "changed", "outdated"}
    return NvidiaFreshnessCheckResponse(
        checked=len(checks),
        up_to_date=sum(1 for check in checks if check.get("status") == "up_to_date"),
        changed=sum(1 for check in checks if check.get("status") in changed_statuses),
        failed=sum(1 for check in checks if check.get("status") == "failed_to_check"),
        persisted=persisted,
        reingested=reingested,
        results=checks,
    )


def run_nvidia_freshness_check(
    settings: Settings,
    *,
    max_sources: int,
    max_chars_per_source: int,
    persist_results: bool,
    reingest_changed: bool = False,
    vector_store: QdrantHttpClient | None = None,
    embedder: EmbeddingProvider | None = None,
) -> NvidiaFreshnessCheckResponse:
    local_snapshots = {}
    if database_enabled(settings):
        try:
            local_snapshots = list_nvidia_document_snapshots(settings)
        except DatabaseUnavailable as error:
            logger.info("NVIDIA freshness snapshot fallback: %s", error)
            local_snapshots = {}

    checks = check_nvidia_sources(
        NVIDIA_TECHNOLOGY_DOCS[:max_sources],
        local_snapshots=local_snapshots,
        max_chars=max_chars_per_source,
    )

    persisted = False
    if persist_results and database_enabled(settings):
        try:
            sync_nvidia_source_registry(settings, NVIDIA_TECHNOLOGY_DOCS)
            save_nvidia_update_checks(settings, checks)
            persisted = True
        except DatabaseUnavailable as error:
            logger.info("NVIDIA freshness checks not persisted: %s", error)
            persisted = False
        except Exception:
            logger.exception("Failed to persist NVIDIA freshness checks.")
            persisted = False

    reingested = 0
    if reingest_changed and vector_store is not None and embedder is not None:
        ingest_urls = {
            str(check.get("source_url"))
            for check in checks
            if check.get("action") == "ingest_candidate"
            and check.get("status") in {"new", "changed", "outdated"}
        }
        ingest_products = {
            str(check.get("product_name"))
            for check in checks
            if check.get("action") == "ingest_candidate"
            and check.get("status") in {"new", "changed", "outdated"}
        }
        documents_to_reingest = [
            document
            for document in NVIDIA_TECHNOLOGY_DOCS
            if document["source_url"] in ingest_urls
            or document["product_name"] in ingest_products
        ]
        if documents_to_reingest:
            result = ingest_nvidia_official_pages(
                vector_store=vector_store,
                embedder=embedder,
                collection_name=settings.nvidia_collection,
                reset_collection=False,
                max_chars_per_source=max_chars_per_source,
                documents=documents_to_reingest,
            )
            reingested = int(result.get("documents") or 0)

    return nvidia_freshness_summary(
        checks,
        persisted=persisted,
        reingested=reingested,
    )


@app.get("/health")
def health(
    settings: Settings = Depends(get_settings),
    vector_store: QdrantHttpClient = Depends(get_vector_store),
) -> dict[str, object]:
    status = "ok"
    try:
        qdrant = vector_store.health()
        qdrant.setdefault("status", "ok")
    except RequestException as error:
        status = "degraded"
        qdrant = {
            "status": "unavailable",
            "url": settings.qdrant_url,
            "error": str(error),
        }

    postgres = database_health(settings)
    if postgres.get("status") not in {"ok", "not_configured"}:
        status = "degraded"

    return {
        "status": status,
        "app": settings.app_name,
        "qdrant": qdrant,
        "postgres": postgres,
        "startup_source": get_startup_catalog_source(settings),
        "embedding": {
            "provider": settings.embedding_provider,
            "model": (
                settings.openai_embedding_model
                if settings.embedding_provider.lower() == "openai"
                else settings.sentence_transformers_model
                if settings.embedding_provider.lower()
                in {"sentence_transformers", "sentence-transformers"}
                else "hash"
            ),
            "vector_size": settings.vector_size,
        },
        "reranker": {
            "provider": settings.reranker_provider,
            "cross_encoder_model": settings.cross_encoder_reranker_model,
            "cross_encoder_local_files_only": settings.cross_encoder_reranker_local_files_only,
        },
        "security": {
            "cors_allow_origins": configured_cors_origins(settings),
            "admin_api_token_configured": bool(settings.admin_api_token),
        },
        "analysis_orchestration": {
            **graph_engine_status(),
            "agents": [
                "Search Planner Agent",
                "Knowledge Freshness Agent",
                "Scraper Agent",
                "Extractor Agent",
                "NVIDIA RAG Agent",
                "Recommendation Agent",
                "Startup Classifier Agent",
                "Evidence Validator Agent",
                "Briefing Agent",
                "Storage Agent",
                "Startup Evidence Agent",
            ],
            "supports_conditions": True,
            "supports_retries": True,
        },
    }


@app.get("/nvidia/technologies", response_model=list[TechnologySummary])
def list_nvidia_technologies() -> list[dict[str, str]]:
    return [
        {
            "product_name": document["product_name"],
            "category": document["category"],
            "source_url": document["source_url"],
            "summary": document["summary"],
        }
        for document in NVIDIA_TECHNOLOGY_DOCS
    ]


@app.post("/rag/ingest/nvidia", response_model=IngestNvidiaResponse)
def ingest_nvidia_knowledge_base(
    request: IngestNvidiaRequest,
    settings: Settings = Depends(get_settings),
    vector_store: QdrantHttpClient = Depends(get_vector_store),
    embedder: EmbeddingProvider = Depends(get_embedder),
    _admin: None = Depends(require_admin_access),
) -> IngestNvidiaResponse:
    try:
        result = ingest_nvidia_seed_documents(
            vector_store=vector_store,
            embedder=embedder,
            collection_name=settings.nvidia_collection,
            reset_collection=request.reset_collection,
        )
    except RequestException as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    return IngestNvidiaResponse(
        collection_name=settings.nvidia_collection,
        documents=result["documents"],
        chunks=result["chunks"],
    )


@app.post("/rag/ingest/nvidia/official", response_model=IngestNvidiaOfficialResponse)
def ingest_nvidia_official_knowledge_base(
    request: IngestNvidiaOfficialRequest,
    settings: Settings = Depends(get_settings),
    vector_store: QdrantHttpClient = Depends(get_vector_store),
    embedder: EmbeddingProvider = Depends(get_embedder),
    _admin: None = Depends(require_admin_access),
) -> IngestNvidiaOfficialResponse:
    try:
        result = ingest_nvidia_official_pages(
            vector_store=vector_store,
            embedder=embedder,
            collection_name=settings.nvidia_collection,
            reset_collection=request.reset_collection,
            max_chars_per_source=request.max_chars_per_source,
            max_chunks_per_source=request.max_chunks_per_source,
        )
    except RequestException as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    if database_enabled(settings):
        try:
            sync_nvidia_source_registry(settings, NVIDIA_TECHNOLOGY_DOCS)
            record_nvidia_document_versions(settings, list(result["sources"]))
        except DatabaseUnavailable as error:
            logger.info("NVIDIA document metadata not persisted: %s", error)
        except Exception:
            logger.exception("Failed to persist NVIDIA document metadata.")

    return IngestNvidiaOfficialResponse(**result)


@app.post("/rag/freshness/check", response_model=NvidiaFreshnessCheckResponse)
def check_nvidia_knowledge_freshness(
    request: NvidiaFreshnessCheckRequest,
    settings: Settings = Depends(get_settings),
    vector_store: QdrantHttpClient = Depends(get_vector_store),
    embedder: EmbeddingProvider = Depends(get_embedder),
    _admin: None = Depends(require_admin_access),
) -> NvidiaFreshnessCheckResponse:
    return run_nvidia_freshness_check(
        settings,
        max_sources=request.max_sources,
        max_chars_per_source=request.max_chars_per_source,
        persist_results=request.persist_results,
        reingest_changed=request.reingest_changed,
        vector_store=vector_store,
        embedder=embedder,
    )


@app.post("/rag/search", response_model=RagSearchResponse)
def search_nvidia_knowledge_base(
    request: RagSearchRequest,
    settings: Settings = Depends(get_settings),
    vector_store: QdrantHttpClient = Depends(get_vector_store),
    embedder: EmbeddingProvider = Depends(get_embedder),
) -> RagSearchResponse:
    try:
        results = vector_store.search(
            collection_name=settings.nvidia_collection,
            vector=embedder.embed(request.query),
            limit=min(20, request.limit * 4),
            filters={"category": request.category} if request.category else None,
        )
    except RequestException as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    parsed_results = []
    seen_products: set[str] = set()
    for result in rerank_recommendation_results(results, request.query, settings):
        payload = result.get("payload") or {}
        product_name = payload.get("product_name", "Unknown")
        if product_name in seen_products:
            continue
        seen_products.add(product_name)
        parsed_results.append(
            RagSearchResult(
                score=result.get("score", 0.0),
                product_name=product_name,
                category=payload.get("category", "unknown"),
                source_url=payload.get("source_url", ""),
                chunk_text=payload.get("chunk_text", ""),
                metadata={
                    "source_type": payload.get("source_type"),
                    "chunk_index": payload.get("chunk_index"),
                    "summary": payload.get("summary"),
                    "collected_at": payload.get("collected_at"),
                    "rerank": result.get("rerank_details"),
                },
            )
        )
        if len(parsed_results) >= request.limit:
            break

    return RagSearchResponse(query=request.query, results=parsed_results)


@app.get("/analysis/runs", response_model=list[AnalysisRunSummary])
def get_analysis_runs(
    limit: int = 20,
    settings: Settings = Depends(get_settings),
) -> list[dict[str, object]]:
    try:
        return list_analysis_runs(settings, limit=max(1, min(limit, 100)))
    except DatabaseUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"Postgres indisponivel: {error}") from error


@app.get("/analysis/runs/{analysis_run_id}/briefing", response_model=AnalysisBriefingResponse)
def get_analysis_briefing_json(
    analysis_run_id: str,
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        briefing = get_analysis_briefing(settings, analysis_run_id)
    except DatabaseUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"Postgres indisponivel: {error}") from error
    if not briefing:
        raise HTTPException(status_code=404, detail="Analise nao encontrada.")
    return briefing


@app.get("/analysis/runs/{analysis_run_id}/briefing.md", response_class=PlainTextResponse)
def download_analysis_briefing_markdown(
    analysis_run_id: str,
    settings: Settings = Depends(get_settings),
) -> PlainTextResponse:
    try:
        briefing = get_analysis_briefing(settings, analysis_run_id)
    except DatabaseUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"Postgres indisponivel: {error}") from error
    if not briefing:
        raise HTTPException(status_code=404, detail="Analise nao encontrada.")

    filename = f"{str(briefing['startup_name']).replace(' ', '_')}_{analysis_run_id}.md"
    return PlainTextResponse(
        str(briefing["briefing_markdown"]),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/analysis/runs/{analysis_run_id}/briefing.pdf")
def download_analysis_briefing_pdf(
    analysis_run_id: str,
    settings: Settings = Depends(get_settings),
) -> Response:
    try:
        briefing = get_analysis_briefing(settings, analysis_run_id)
    except DatabaseUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"Postgres indisponivel: {error}") from error
    if not briefing:
        raise HTTPException(status_code=404, detail="Analise nao encontrada.")

    filename = f"{str(briefing['startup_name']).replace(' ', '_')}_{analysis_run_id}.pdf"
    return Response(
        build_pdf(str(briefing["briefing_markdown"])),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/startup/evidence/search", response_model=StartupEvidenceSearchResponse)
def search_startup_evidence(
    request: StartupEvidenceSearchRequest,
    settings: Settings = Depends(get_settings),
    vector_store: QdrantHttpClient = Depends(get_vector_store),
    embedder: EmbeddingProvider = Depends(get_embedder),
) -> StartupEvidenceSearchResponse:
    filters = {
        "startup_name": request.startup_name,
        "analysis_run_id": request.analysis_run_id,
    }
    try:
        results = vector_store.search(
            collection_name=settings.startup_collection,
            vector=embedder.embed(request.query),
            limit=request.limit,
            filters=filters,
        )
    except RequestException as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    parsed_results = []
    for result in results:
        payload = result.get("payload") or {}
        parsed_results.append(
            StartupEvidenceSearchResult(
                score=result.get("score", 0.0),
                startup_name=payload.get("startup_name", "Unknown"),
                analysis_run_id=payload.get("analysis_run_id", ""),
                source_url=payload.get("source_url", ""),
                chunk_text=payload.get("chunk_text", ""),
                metadata={
                    "source_type": payload.get("source_type"),
                    "chunk_index": payload.get("chunk_index"),
                    "status_code": payload.get("status_code"),
                    "characters": payload.get("characters"),
                    "collected_at": payload.get("collected_at"),
                },
            )
        )

    return StartupEvidenceSearchResponse(query=request.query, results=parsed_results)


def score_startup_profile(text: str, recommendation_count: int) -> tuple[str, int, int, int]:
    lower_text = unicodedata.normalize("NFKD", text.lower())
    lower_text = "".join(
        character for character in lower_text if not unicodedata.combining(character)
    )

    def contains_term(term: str) -> bool:
        if len(term) <= 3 and term.isalnum():
            return bool(re.search(rf"\b{re.escape(term)}\b", lower_text))
        return term in lower_text

    ai_terms = [
        "ai",
        "ia",
        "inteligencia artificial",
        "machine learning",
        "llm",
        "modelo de ia",
        "modelos de ia",
        "modelo preditivo",
        "generative",
        "visao computacional",
        "nlp",
        "agent",
    ]
    depth_terms = [
        "dados proprietarios",
        "workflow",
        "pipeline",
        "producao",
        "inferencia",
        "latencia",
        "escala",
        "governanca",
    ]
    wrapper_terms = ["chatbot", "wrapper", "api externa", "openai", "interface"]
    business_context_terms = [
        "startup",
        "empresa",
        "produto",
        "plataforma",
        "software",
        "saas",
        "marketplace",
        "fintech",
        "healthtech",
        "logistica",
        "educacao",
        "ecommerce",
        "pagamentos",
        "gestao",
        "clientes",
        "operacao",
    ]

    ai_signal = sum(1 for term in ai_terms if contains_term(term))
    depth_signal = sum(1 for term in depth_terms if contains_term(term))
    wrapper_signal = sum(1 for term in wrapper_terms if contains_term(term))
    context_signal = sum(1 for term in business_context_terms if contains_term(term))
    word_count = len(lower_text.split())
    has_meaningful_business_context = word_count >= 18 or (
        word_count >= 10 and context_signal > 0
    )

    ai_native_score = min(100, 20 + ai_signal * 9 + depth_signal * 8)
    wrapper_risk_score = min(100, wrapper_signal * 18 + max(0, 30 - depth_signal * 8))
    nvidia_fit_score = min(100, int(ai_native_score * 0.55 + recommendation_count * 10))

    if ai_signal == 0 and wrapper_signal == 0 and has_meaningful_business_context:
        classification = "non_ai"
    elif ai_native_score >= 70 and wrapper_risk_score < 50:
        classification = "ai_native"
    elif wrapper_risk_score >= 60:
        classification = "wrapper_risk"
    elif ai_native_score >= 45:
        classification = "ai_enabled"
    else:
        classification = "insufficient_evidence"

    return classification, ai_native_score, wrapper_risk_score, nvidia_fit_score


def normalize_text(text: str) -> str:
    lower_text = unicodedata.normalize("NFKD", text.lower())
    return "".join(
        character for character in lower_text if not unicodedata.combining(character)
    )


def recommendation_boost(product_name: str, category: str, profile_text: str) -> float:
    return enhanced_recommendation_boost(product_name, category, profile_text)


def rerank_score(result: dict[str, object], profile_text: str) -> float:
    payload = result.get("payload") or {}
    if not isinstance(payload, dict):
        return float(result.get("score") or 0.0)

    return float(result.get("score") or 0.0) + recommendation_boost(
        str(payload.get("product_name", "")),
        str(payload.get("category", "")),
        profile_text,
    )


def rerank_recommendation_results(
    results: list[dict[str, object]],
    profile_text: str,
    settings: Settings | None = None,
) -> list[dict[str, object]]:
    return rerank_results(
        results,
        profile_text,
        provider=settings.reranker_provider if settings else "hybrid",
        cross_encoder_model=(
            settings.cross_encoder_reranker_model
            if settings
            else "cross-encoder/ms-marco-MiniLM-L-6-v2"
        ),
        cross_encoder_local_files_only=(
            settings.cross_encoder_reranker_local_files_only if settings else True
        ),
    )


def build_candidate_profile(candidate: dict[str, object], focus: str | None = None) -> str:
    parts = [
        str(candidate.get("startup_name", "")),
        str(candidate.get("sector", "")),
        str(candidate.get("description", "")),
        " ".join(str(signal) for signal in candidate.get("signals", [])),
        focus or "",
    ]
    return " ".join(part for part in parts if part).strip()


def candidate_prefilter_score(candidate: dict[str, object], focus: str | None = None) -> int:
    profile_text = build_candidate_profile(candidate, focus)
    _classification, ai_native_score, wrapper_risk_score, nvidia_fit_score = (
        score_startup_profile(profile_text, 0)
    )
    signal_score = min(100, 45 + len(candidate.get("signals", [])) * 7)
    focus_score = 0
    if focus:
        profile_terms = set(normalize_text(profile_text).split())
        focus_terms = set(normalize_text(focus).split())
        focus_score = len(profile_terms & focus_terms) * 6

    return round(
        ai_native_score * 0.4
        + nvidia_fit_score * 0.3
        + signal_score * 0.25
        + focus_score
        - wrapper_risk_score * 0.1
    )


def dedupe_startup_candidates(
    candidates: list[dict[str, object]],
    focus: str | None = None,
) -> list[dict[str, object]]:
    best_by_key: dict[str, tuple[tuple[int, int], dict[str, object]]] = {}
    for candidate in candidates:
        key = startup_key(candidate.get("startup_name")) or normalize_text(
            str(candidate.get("website_url") or candidate.get("source_url") or "")
        )
        if not key:
            key = str(id(candidate))
        score = (
            candidate_prefilter_score(candidate, focus),
            startup_source_confidence(candidate),
        )
        current = best_by_key.get(key)
        if current is None or score > current[0]:
            best_by_key[key] = (score, candidate)
    return [candidate for _score, candidate in best_by_key.values()]


def opportunity_timing(
    *,
    opportunity_percent: int,
    nvidia_fit_score: int,
    wrapper_risk_score: int,
    recommendation_count: int,
    signal_count: int,
) -> str:
    if (
        opportunity_percent >= 72
        and nvidia_fit_score >= 70
        and recommendation_count >= 2
        and signal_count >= 2
        and wrapper_risk_score < 65
    ):
        return "quente"
    if opportunity_percent >= 52 and nvidia_fit_score >= 55 and recommendation_count >= 1:
        return "morno"
    return "exploratorio"


def is_brazilian_candidate(candidate: dict[str, object]) -> bool:
    country_code = str(candidate.get("country_code", "")).upper()
    if country_code == "BR":
        return True

    searchable = normalize_text(build_candidate_profile(candidate))
    return any(
        term in searchable
        for term in ("brasil", "brazil", "brasileira", "brasileiro", "brasileiras")
    )


def candidate_matches(
    candidate: dict[str, object],
    sector: str | None,
    focus: str | None,
    stage: str | None = None,
) -> bool:
    if not sector and not focus and not stage:
        return True

    searchable = normalize_text(build_candidate_profile(candidate))
    if stage and normalize_text(stage) != normalize_text(str(candidate.get("stage", ""))):
        return False
    sector_aliases = {
        "cyber": "cybersecurity security seguranca threat fraude anomaly",
        "ciber": "cybersecurity security seguranca threat fraude anomaly",
        "seguranca": "cybersecurity security seguranca threat fraude anomaly",
        "saude": "healthcare health clinico clinical medico",
        "health": "healthcare health clinico clinical medico",
        "logistica": "logistics logistica routing rotas scheduling",
        "logistics": "logistics logistica routing rotas scheduling",
        "dados": "data analytics tabular pandas machine learning",
        "data": "data analytics tabular pandas machine learning",
        "educacao": "education edtech educacao educacional ensino professor aluno",
        "education": "education edtech educacao educacional ensino professor aluno",
        "devtools": "developer_tools developer tools agents rag copilot",
        "robotica": "robotics robotica simulation digital twin",
        "vision": "computer_vision computer vision edge video",
        "voz": "speech voice call center asr tts",
    }

    if sector:
        normalized_sector = normalize_text(sector)
        sector_terms = sector_aliases.get(normalized_sector, normalized_sector)
        if not any(term in searchable for term in sector_terms.split()):
            return False
    if focus and not any(term in searchable for term in normalize_text(focus).split()):
        return False
    return True


def percent_from_tool_result(result: dict[str, object], profile_text: str) -> int:
    payload = result.get("payload") or {}
    if not isinstance(payload, dict):
        return 0

    raw_score = float(result.get("score") or 0.0)
    boost = recommendation_boost(
        str(payload.get("product_name", "")),
        str(payload.get("category", "")),
        profile_text,
    )
    return max(35, min(99, round(raw_score * 92 + boost * 35)))


def local_tool_fit_score(document: dict[str, str], profile_text: str) -> float:
    profile_terms = {
        term for term in normalize_text(profile_text).split() if len(term) > 2
    }
    document_terms = {
        term
        for term in normalize_text(
            " ".join(
                [
                    document["product_name"],
                    document["category"],
                    document["summary"],
                    document["text"],
                ]
            )
        ).split()
        if len(term) > 2
    }
    overlap = len(profile_terms & document_terms)
    return overlap * 0.04 + recommendation_boost(
        document["product_name"],
        document["category"],
        profile_text,
    )


def build_local_tool_fits(profile_text: str) -> list[StartupRadarToolFit]:
    ranked_documents = sorted(
        NVIDIA_TECHNOLOGY_DOCS,
        key=lambda document: local_tool_fit_score(document, profile_text),
        reverse=True,
    )

    tools = []
    for document in ranked_documents[:3]:
        score = local_tool_fit_score(document, profile_text)
        tools.append(
            StartupRadarToolFit(
                technology=document["product_name"],
                category=document["category"],
                fit_percent=max(35, min(99, round(45 + score * 70))),
                source_url=document["source_url"],
                reason=document["summary"],
            )
        )
    return tools


def candidate_to_search_result(candidate: dict[str, object]) -> StartupSearchResult:
    return StartupSearchResult(
        startup_name=str(candidate.get("startup_name", "")),
        country_code=str(candidate.get("country_code", "") or "") or None,
        sector=str(candidate.get("sector", "unknown")),
        stage=candidate.get("stage"),
        source=str(candidate.get("source", "unknown")),
        website_url=candidate.get("website_url"),
        github_url=candidate.get("github_url"),
        source_url=candidate.get("source_url"),
        description=str(candidate.get("description", "")),
        signals=[str(signal) for signal in candidate.get("signals", [])],
        match_score=int(candidate.get("match_score") or 0),
    )


def discovery_to_result(discovery: dict[str, object]) -> StartupDiscoveryResult:
    return StartupDiscoveryResult(
        startup_name=str(discovery.get("startup_name", "")),
        country_code=str(discovery.get("country_code") or "") or None,
        sector=str(discovery.get("sector") or "unknown"),
        stage=str(discovery.get("stage") or "") or None,
        source=str(discovery.get("source") or "unknown"),
        website_url=discovery.get("website_url") or None,
        github_url=discovery.get("github_url") or None,
        source_url=discovery.get("source_url") or None,
        article_title=str(discovery.get("article_title") or discovery.get("description") or ""),
        article_url=str(discovery.get("article_url") or discovery.get("source_url") or ""),
        description=str(discovery.get("description") or ""),
        signals=[str(signal) for signal in discovery.get("signals", [])],
        confidence=int(discovery.get("confidence") or 0),
        discovered_at=str(discovery.get("discovered_at") or ""),
        status=str(discovery.get("status") or "unknown"),
    )


@app.post("/startups/search", response_model=StartupSearchResponse)
def search_startups(
    request: StartupSearchRequest,
    settings: Settings = Depends(get_settings),
) -> StartupSearchResponse:
    source_status = get_startup_catalog_source(settings)
    candidates = get_active_startup_candidates(settings)
    results = search_startup_candidates(candidates, request.query, request.limit)
    return StartupSearchResponse(
        query=request.query,
        source=str(source_status["source"]),
        source_path=str(source_status["source_path"]),
        total_candidates=len(candidates),
        returned=len(results),
        results=[candidate_to_search_result(candidate) for candidate in results],
    )


@app.get("/startup/repertoire", response_model=StartupRepertoireResponse)
def get_startup_repertoire(
    settings: Settings = Depends(get_settings),
) -> StartupRepertoireResponse:
    if database_enabled(settings):
        discoveries = list_startup_discoveries(settings)
        discovery_path = "startup_discoveries"
    else:
        discoveries = read_discoveries(settings.startup_discovery_path)
        discovery_path = str(startup_source_status(settings.startup_discovery_path)["path"])
    return StartupRepertoireResponse(
        source_url=", ".join(configured_discovery_sources(settings)),
        discovery_path=discovery_path,
        total=len(discoveries),
        results=[discovery_to_result(discovery) for discovery in discoveries],
    )


@app.post("/startup/repertoire/refresh", response_model=StartupRepertoireRefreshResponse)
def refresh_startup_repertoire(
    request: StartupRepertoireRefreshRequest,
    settings: Settings = Depends(get_settings),
    _admin: None = Depends(require_admin_access),
) -> StartupRepertoireRefreshResponse:
    try:
        source_urls = configured_discovery_sources(settings)
        if database_enabled(settings):
            collection = collect_discoveries_from_sources(source_urls, max_items=request.max_items)
            found = list(collection["results"])
            added = upsert_startup_discoveries(settings, found)
            discoveries = list_startup_discoveries(settings)
            result = {
                "source_url": ", ".join(source_urls),
                "found": len(found),
                "added": added,
                "total": len(discoveries),
                "results": discoveries[: request.max_items],
            }
        else:
            result = refresh_discovery_repertoire(
                source_url=settings.startup_discovery_source_url,
                source_urls=source_urls,
                discovery_path=settings.startup_discovery_path,
                max_items=request.max_items,
            )
    except RequestException as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    return StartupRepertoireRefreshResponse(
        source_url=str(result["source_url"]),
        found=int(result["found"]),
        added=int(result["added"]),
        total=int(result["total"]),
        results=[discovery_to_result(discovery) for discovery in result["results"]],
    )


@app.post("/startup/repertoire/use", response_model=StartupRepertoireUseResponse)
def use_startup_repertoire(
    request: StartupRepertoireUseRequest,
    settings: Settings = Depends(get_settings),
    _admin: None = Depends(require_admin_access),
) -> StartupRepertoireUseResponse:
    if database_enabled(settings):
        result = promote_startup_discoveries_to_catalog(
            settings,
            min_confidence=request.min_confidence,
        )
    else:
        result = use_discovered_startups(
            discovery_path=settings.startup_discovery_path,
            startup_source_path=settings.startup_source_path,
            min_confidence=request.min_confidence,
        )
    return StartupRepertoireUseResponse(
        imported=int(result["imported"]),
        skipped=int(result["skipped"]),
        total_active=int(result["total_active"]),
        results=[candidate_to_search_result(candidate) for candidate in result["results"]],
    )


@app.post("/startup/repertoire/enrich", response_model=StartupRepertoireEnrichResponse)
def enrich_startup_repertoire(
    request: StartupRepertoireEnrichRequest,
    settings: Settings = Depends(get_settings),
    _admin: None = Depends(require_admin_access),
) -> StartupRepertoireEnrichResponse:
    if database_enabled(settings):
        discoveries = list_startup_discoveries(settings)
        result = enrich_discoveries(discoveries, max_items=request.max_items)
        updated = result["results"]
        if updated:
            upsert_startup_discoveries(settings, updated)
            enriched_candidates = [
                catalog_candidate_from_discovery(discovery, source_prefix="enriched")
                for discovery in updated
                if discovery.get("status") == "enriched"
            ]
            if enriched_candidates:
                upsert_startup_catalog(settings, enriched_candidates)
    else:
        discoveries = read_discoveries(settings.startup_discovery_path)
        result = enrich_discoveries(discoveries, max_items=request.max_items)
        updated_by_key = {
            f"{discovery.get('startup_name')}|{discovery.get('article_url') or discovery.get('source_url')}": discovery
            for discovery in result["results"]
        }
        merged = [
            updated_by_key.get(
                f"{discovery.get('startup_name')}|{discovery.get('article_url') or discovery.get('source_url')}",
                discovery,
            )
            for discovery in discoveries
        ]
        write_discoveries(settings.startup_discovery_path, merged)

    return StartupRepertoireEnrichResponse(
        processed=int(result["processed"]),
        enriched=int(result["enriched"]),
        needs_review=int(result["needs_review"]),
        failed=int(result["failed"]),
        results=[discovery_to_result(discovery) for discovery in result["results"]],
    )


@app.post("/startup/repertoire/review", response_model=StartupRepertoireReviewResponse)
def review_startup_repertoire_item(
    request: StartupRepertoireReviewRequest,
    settings: Settings = Depends(get_settings),
    _admin: None = Depends(require_admin_access),
) -> StartupRepertoireReviewResponse:
    target = {
        "startup_name": request.startup_name,
        "article_url": str(request.article_url or ""),
    }
    target_key = discovery_key(target)

    if database_enabled(settings):
        discoveries = list_startup_discoveries(settings)
    else:
        discoveries = read_discoveries(settings.startup_discovery_path)

    selected = None
    for discovery in discoveries:
        same_name = discovery_key(discovery) == target_key
        same_article = not request.article_url or str(discovery.get("article_url") or "") == str(
            request.article_url
        )
        if same_name and same_article:
            selected = discovery
            break

    if not selected:
        raise HTTPException(status_code=404, detail="Descoberta nao encontrada no repertorio.")

    try:
        reviewed = review_discovery_with_website(
            selected,
            str(request.website_url),
            sector=request.sector,
            stage=request.stage,
            description=request.description,
            signals=request.signals,
        )
    except RequestException as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except BrazilianStartupValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    promoted = False
    if database_enabled(settings):
        upsert_startup_discoveries(settings, [reviewed])
        if request.promote and reviewed.get("status") == "enriched":
            upsert_startup_catalog(
                settings,
                [catalog_candidate_from_discovery(reviewed, source_prefix="reviewed")],
            )
            promoted = True
    else:
        reviewed_key = discovery_key(reviewed)
        merged = [
            reviewed if discovery_key(discovery) == reviewed_key else discovery
            for discovery in discoveries
        ]
        write_discoveries(settings.startup_discovery_path, merged)
        if request.promote and reviewed.get("status") == "enriched":
            use_discovered_startups(
                discovery_path=settings.startup_discovery_path,
                startup_source_path=settings.startup_source_path,
                min_confidence=50,
            )
            promoted = True

    return StartupRepertoireReviewResponse(
        promoted=promoted,
        result=discovery_to_result(reviewed),
    )


@app.post("/startup/radar", response_model=StartupRadarResponse)
def startup_radar(
    request: StartupRadarRequest,
    settings: Settings = Depends(get_settings),
) -> StartupRadarResponse:
    all_candidates = get_active_startup_candidates(settings)
    source_status = get_startup_catalog_source(settings)
    candidates = [
        candidate
        for candidate in all_candidates
        if is_brazilian_candidate(candidate)
        and candidate_matches(candidate, request.sector, request.focus, request.stage)
    ]
    if not candidates:
        candidates = [candidate for candidate in all_candidates if is_brazilian_candidate(candidate)]
    candidates = dedupe_startup_candidates(candidates, request.focus)

    candidates_to_score = sorted(
        candidates,
        key=lambda candidate: candidate_prefilter_score(candidate, request.focus),
        reverse=True,
    )[: request.limit]

    ranked: list[StartupRadarResult] = []
    for candidate in candidates_to_score:
        profile_text = build_candidate_profile(candidate, request.focus)
        top_tools = build_local_tool_fits(profile_text)

        classification, ai_native_score, wrapper_risk_score, nvidia_fit_score = (
            score_startup_profile(profile_text, len(top_tools))
        )
        average_tool_fit = (
            sum(tool.fit_percent for tool in top_tools) / len(top_tools)
            if top_tools
            else 0
        )
        signal_score = min(100, 45 + len(candidate.get("signals", [])) * 7)
        opportunity_percent = max(
            0,
            min(
                99,
                round(
                    nvidia_fit_score * 0.45
                    + average_tool_fit * 0.4
                    + signal_score * 0.15
                    - wrapper_risk_score * 0.12
                ),
            ),
        )
        approach_timing = opportunity_timing(
            opportunity_percent=opportunity_percent,
            nvidia_fit_score=nvidia_fit_score,
            wrapper_risk_score=wrapper_risk_score,
            recommendation_count=len(top_tools),
            signal_count=len(candidate.get("signals", [])),
        )
        ranked.append(
            StartupRadarResult(
                startup_name=str(candidate["startup_name"]),
                sector=str(candidate.get("sector", "unknown")),
                stage=candidate.get("stage"),
                source=str(candidate.get("source", "unknown")),
                website_url=candidate.get("website_url"),
                github_url=candidate.get("github_url"),
                source_url=candidate.get("source_url"),
                opportunity_percent=opportunity_percent,
                approach_timing=approach_timing,
                ai_native_score=ai_native_score,
                nvidia_fit_score=nvidia_fit_score,
                wrapper_risk_score=wrapper_risk_score,
                source_confidence=startup_source_confidence(candidate),
                source_summary=startup_source_summary(candidate),
                source_evidence=build_startup_source_evidence(candidate),
                top_tools=top_tools,
                evidence_summary=str(candidate.get("description", "")),
                signals=[str(signal) for signal in candidate.get("signals", [])],
            )
        )

    ranked.sort(key=lambda item: item.opportunity_percent, reverse=True)
    limited = ranked[: request.limit]
    return StartupRadarResponse(
        source=str(source_status["source"]),
        total_candidates=len(candidates),
        returned=len(limited),
        results=limited,
    )


@app.post("/analysis/startup", response_model=StartupAnalysisResponse)
def analyze_startup(
    request: StartupAnalysisRequest,
    settings: Settings = Depends(get_settings),
    vector_store: QdrantHttpClient = Depends(get_vector_store),
    embedder: EmbeddingProvider = Depends(get_embedder),
) -> StartupAnalysisResponse:
    try:
        return run_startup_analysis_graph(
            request=request,
            settings=settings,
            vector_store=vector_store,
            embedder=embedder,
            startup_candidate_loader=get_active_startup_candidates,
            nvidia_freshness_runner=run_nvidia_freshness_check,
            score_startup_profile=score_startup_profile,
            rerank_recommendation_results=rerank_recommendation_results,
        )
    except RequestException as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except BrazilianStartupValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
