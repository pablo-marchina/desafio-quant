from datetime import datetime, timezone
from app.discovery import discover_sources
from fastapi import FastAPI, HTTPException, Query
from app.research import run_research_pipeline
from app.recommendation import generate_recommendations
from app.briefing import build_briefing
from app.workflow import startup_radar_graph
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.database import check_database_connection

from app.collector import collect_source
from app.evidence import build_evidences
from app.schemas import (
    AnalyzeMultipleRequest,
    AnalyzeMultipleResponse,
    AnalyzeResponse,
    CollectRequest,
    CollectResponse,
    SourceCollectionStatus,
    DiscoverSourcesRequest,
    DiscoverSourcesResponse,
    ResearchRequest,
    ResearchResponse
)
from app.scoring import calculate_scores
from app.rag.ingest import ingest_nvidia_knowledge_base
from app.rag.schemas import (
    BriefingResponse,
    FullAnalysisResponse,
    NvidiaIngestResponse,
    NvidiaRagQueryRequest,
    NvidiaRagQueryResponse,
    ResearchWithNvidiaContextResponse,
    RecommendationResponse,
    AnalysisHistoryItem,
    SavedBriefingResponse,
    StartupAnalysesResponse,
    StartupListResponse,
)
from app.rag.service import run_nvidia_rag

from app.nvidia_context import (
    build_research_with_nvidia_context,
)

from uuid import UUID, uuid4

from app.persistence import (
    PersistenceError,
    persist_full_analysis,
)

from app.history import (
    HistoryError,
    HistoryNotFoundError,
    get_analysis,
    get_saved_briefing,
    list_startup_analyses,
    list_startups,
)

from fastapi.responses import StreamingResponse

from app.pdf_report import (
    PdfReportError,
    build_full_analysis_pdf,
    safe_pdf_filename,
)

app = FastAPI(
    title="NVIDIA Startup AI Radar",
    version="0.3.0",
    description="API para coletar, analisar e identificar sinais públicos sobre startups."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "project": "NVIDIA Startup AI Radar",
        "status": "running",
        "available_endpoints": [
            "POST /collect",
            "POST /analyze",
            "POST /analyze-multiple",
            "POST /discover-sources",
            "POST /research",
            "POST /nvidia-rag/ingest",
            "POST /nvidia-rag",
            "POST /research/nvidia-context",
            "POST /research/recommendations",
            "POST /research/briefing",
            "POST /research/full",
            "GET /database/health",
            "GET /startups",
            "GET /startups/{startup_id}/analyses",
            "GET /analyses/{analysis_id}",
            "GET /analyses/{analysis_id}/briefing",
            "GET /analyses/{analysis_id}/full"
            "GET /analyses/{analysis_id}/report.pdf",
        ]
    }

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post(
    "/discover-sources",
    response_model=DiscoverSourcesResponse
)
async def discover_public_sources(payload: DiscoverSourcesRequest):
    return await discover_sources(payload)


@app.post("/research", response_model=ResearchResponse)
async def run_research(payload: ResearchRequest):
    return await run_research_pipeline(payload)

@app.post("/collect", response_model=CollectResponse)
async def collect_public_source(payload: CollectRequest):
    return await collect_source(
        startup_name=payload.startup_name,
        url=str(payload.url)
    )


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_startup(payload: CollectRequest):
    collected = await collect_source(
        startup_name=payload.startup_name,
        url=str(payload.url)
    )

    evidences, ai_signals = build_evidences(
        clean_text=collected.clean_text,
        source_url=collected.source.url
    )

    classification = calculate_scores(
        clean_text=collected.clean_text,
        ai_signals=ai_signals
    )

    return AnalyzeResponse(
        startup_name=collected.startup_name,
        source=collected.source,
        collected_at=collected.collected_at,
        classification=classification,
        evidences=evidences,
        ai_signals_found=ai_signals,
        clean_text_preview=collected.clean_text[:1000]
    )


@app.post("/analyze-multiple", response_model=AnalyzeMultipleResponse)
async def analyze_multiple_sources(payload: AnalyzeMultipleRequest):
    successful_collections = []
    source_statuses = []
    seen_urls = set()

    for url_item in payload.urls:
        url = str(url_item)

        if url in seen_urls:
            continue

        seen_urls.add(url)

        try:
            collected = await collect_source(
                startup_name=payload.startup_name,
                url=url
            )

            successful_collections.append(collected)

            source_statuses.append(
                SourceCollectionStatus(
                    url=collected.source.url,
                    status="COLLECTED",
                    title=collected.source.title,
                    extraction_method=collected.source.extraction_method,
                    text_characters=collected.text_characters,
                    word_count=collected.word_count
                )
            )

        except HTTPException as error:
            source_statuses.append(
                SourceCollectionStatus(
                    url=url,
                    status="FAILED",
                    error=str(error.detail)
                )
            )

    if not successful_collections:
        raise HTTPException(
            status_code=422,
            detail=(
                "Nenhuma das fontes fornecidas pôde ser coletada. "
                "Verifique as URLs ou tente outras fontes públicas."
            )
        )

    all_evidences = []
    all_ai_signals = []

    for collected in successful_collections:
        evidences, ai_signals = build_evidences(
            clean_text=collected.clean_text,
            source_url=collected.source.url
        )

        all_evidences.extend(evidences)
        all_ai_signals.extend(ai_signals)

    unique_ai_signals = sorted(set(all_ai_signals))

    combined_text = "\n\n".join(
        collection.clean_text
        for collection in successful_collections
    )

    classification = calculate_scores(
        clean_text=combined_text,
        ai_signals=unique_ai_signals
    )

    successful_count = len(successful_collections)
    failed_count = len(source_statuses) - successful_count

    return AnalyzeMultipleResponse(
        startup_name=payload.startup_name,
        collected_at=datetime.now(timezone.utc),
        sources=source_statuses,
        sources_successful=successful_count,
        sources_failed=failed_count,
        classification=classification,
        evidences=all_evidences,
        ai_signals_found=unique_ai_signals,
        clean_text_preview=combined_text[:1500]
    )

@app.post(
    "/nvidia-rag/ingest",
    response_model=NvidiaIngestResponse,
    tags=["NVIDIA RAG"],
)
async def ingest_nvidia_rag():
    return await ingest_nvidia_knowledge_base()

@app.post(
    "/nvidia-rag",
    response_model=NvidiaRagQueryResponse,
    tags=["NVIDIA RAG"],
)
async def query_nvidia_rag(
    payload: NvidiaRagQueryRequest,
):
    return run_nvidia_rag(payload)

@app.post(
    "/research/nvidia-context",
    response_model=ResearchWithNvidiaContextResponse,
    tags=["NVIDIA RAG"],
)
async def research_with_nvidia_context(
    payload: ResearchRequest,
):
    research = await run_research_pipeline(payload)

    return build_research_with_nvidia_context(
        research
    )

@app.post(
    "/research/recommendations",
    response_model=RecommendationResponse,
    tags=["Recommendations"],
)
async def research_recommendations(
    payload: ResearchRequest,
):
    research = await run_research_pipeline(payload)

    research_with_context = (
        build_research_with_nvidia_context(research)
    )

    return await generate_recommendations(
        research_with_context
    )

@app.post(
    "/research/briefing",
    response_model=BriefingResponse,
    tags=["Briefing"],
)
async def research_briefing(
    payload: ResearchRequest,
):
    research = await run_research_pipeline(payload)

    research_with_context = (
        build_research_with_nvidia_context(research)
    )

    recommendations = await generate_recommendations(
        research_with_context
    )

    return build_briefing(
        research_with_context=research_with_context,
        recommendation_response=recommendations,
    )

@app.post(
    "/research/full",
    response_model=FullAnalysisResponse,
    tags=["Workflow"],
)
async def research_full(
    payload: ResearchRequest,
):
    final_state = await startup_radar_graph.ainvoke(
        {
            "payload": payload,
        }
    )

    research_with_context = final_state[
        "research_with_context"
    ]

    full_analysis = FullAnalysisResponse(
        analysis_id=str(uuid4()),
        research=final_state["research"],
        nvidia_context=research_with_context.nvidia_context,
        recommendations=final_state["recommendations"],
        briefing=final_state["briefing"],
    )

    try:
        await persist_full_analysis(
            final_analysis=full_analysis,
            sector=payload.sector,
        )

    except PersistenceError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error

    return full_analysis

@app.get(
    "/database/health",
    tags=["Database"],
)
async def database_health():
    try:
        return check_database_connection()

    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "Não foi possível conectar ao Supabase: "
                f"{error}"
            ),
        ) from error
    
@app.get(
    "/startups",
    response_model=StartupListResponse,
    tags=["History"],
)
async def get_startups(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
):
    try:
        return await list_startups(limit)

    except HistoryError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error


@app.get(
    "/startups/{startup_id}/analyses",
    response_model=StartupAnalysesResponse,
    tags=["History"],
)
async def get_startup_history(
    startup_id: UUID,
):
    try:
        return await list_startup_analyses(
            str(startup_id)
        )

    except HistoryNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    except HistoryError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error


@app.get(
    "/analyses/{analysis_id}",
    response_model=FullAnalysisResponse,
    tags=["History"],
)
async def get_saved_analysis(
    analysis_id: UUID,
):
    try:
        return await get_analysis(
            str(analysis_id)
        )

    except HistoryNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    except HistoryError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error


@app.get(
    "/analyses/{analysis_id}/briefing",
    response_model=SavedBriefingResponse,
    tags=["History"],
)
async def get_analysis_briefing(
    analysis_id: UUID,
):
    try:
        return await get_saved_briefing(
            str(analysis_id)
        )

    except HistoryNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    except HistoryError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error
    
@app.get(
    "/analyses/{analysis_id}/report.pdf",
    tags=["Reports"],
)
async def download_analysis_report(
    analysis_id: UUID,
):
    try:
        analysis = await get_analysis(str(analysis_id))

        pdf_content = build_full_analysis_pdf(analysis)

        filename = (
            "nvidia-startup-radar-"
            f"{safe_pdf_filename(analysis.research.startup_name)}.pdf"
        )

        return StreamingResponse(
            iter([pdf_content]),
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{filename}"'
                ),
                "Cache-Control": "no-store, max-age=0",
            },
        )

    except HistoryNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    except HistoryError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error

    except PdfReportError as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error
