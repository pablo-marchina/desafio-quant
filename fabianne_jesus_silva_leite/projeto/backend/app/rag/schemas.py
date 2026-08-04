from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

from app.schemas import ResearchResponse


class NvidiaSource(BaseModel):
    technology_id: str
    technology_name: str
    title: str
    source_url: HttpUrl
    source_type: str
    tags: list[str]
    enabled: bool = True


class NvidiaChunk(BaseModel):
    chunk_id: str
    technology_id: str
    technology_name: str
    title: str
    text: str
    source_url: str
    source_type: str
    tags: list[str]
    chunk_index: int
    word_count: int
    collected_at: datetime


class NvidiaIngestStatus(BaseModel):
    technology_id: str
    technology_name: str
    source_url: str
    status: str
    chunks_created: int = 0
    text_characters: int = 0
    error: str | None = None


class NvidiaIngestResponse(BaseModel):
    collected_at: datetime
    sources_processed: int
    sources_successful: int
    sources_failed: int
    chunks_created: int
    embedding_model: str
    statuses: list[NvidiaIngestStatus]


class NvidiaRagQueryRequest(BaseModel):
    query: str = Field(min_length=10, max_length=1500)
    top_k: int = Field(default=3, ge=1, le=8)


class HybridCandidate(BaseModel):
    chunk_id: str
    technology_id: str
    technology_name: str
    title: str
    text: str
    source_url: str
    source_type: str
    tags: list[str]
    lexical_score: float
    semantic_score: float
    fused_score: float
    rerank_score: float | None = None


class NvidiaRagResult(BaseModel):
    technology_id: str
    technology_name: str
    title: str
    text: str
    source_url: str
    tags: list[str]
    lexical_score: float
    semantic_score: float
    fused_score: float
    rerank_score: float


class NvidiaRagQueryResponse(BaseModel):
    query: str
    pipeline: str
    retrieved_at: datetime
    results: list[NvidiaRagResult]


class NvidiaContextTechnology(BaseModel):
    technology_id: str
    technology_name: str
    why_retrieved: list[str]
    evidences: list[NvidiaRagResult]


class NvidiaContextResponse(BaseModel):
    generated_queries: list[str]
    technologies: list[NvidiaContextTechnology]


class ResearchWithNvidiaContextResponse(BaseModel):
    research: ResearchResponse
    nvidia_context: NvidiaContextResponse


class RecommendationCitation(BaseModel):
    evidence_id: str
    source_type: Literal["startup", "nvidia"]
    source_url: str
    quote: str


class NvidiaRecommendation(BaseModel):
    technology_id: str
    technology_name: str
    priority: Literal["ALTA", "MEDIA", "BAIXA"]
    technical_reason: str
    business_reason: str
    complexity: Literal["BAIXA", "MEDIA", "ALTA"]
    next_action: str
    startup_evidences: list[RecommendationCitation]
    nvidia_evidences: list[RecommendationCitation]


class RecommendationResponse(BaseModel):
    model: str
    recommendations: list[NvidiaRecommendation]
    limitations: list[str]


class FlightPlanPhase(BaseModel):
    period: Literal["0-30 dias", "31-60 dias", "61-90 dias"]
    title: str
    objective: str
    actions: list[str] = Field(default_factory=list)
    nvidia_technologies: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)


class FlightPlanResponse(BaseModel):
    title: str = "NVIDIA Flight Plan - 90 dias"
    summary: str = ""
    phases: list[FlightPlanPhase] = Field(default_factory=list)


class BriefingResponse(BaseModel):
    startup_name: str
    generated_at: datetime
    recommendation_count: int
    markdown: str
    flight_plan: FlightPlanResponse = Field(
        default_factory=FlightPlanResponse,
    )


class FullAnalysisResponse(BaseModel):
    analysis_id: str
    research: ResearchResponse
    nvidia_context: NvidiaContextResponse
    recommendations: RecommendationResponse
    briefing: BriefingResponse


class StartupHistoryItem(BaseModel):
    startup_id: str
    name: str
    sector: str | None = None
    created_at: datetime
    latest_analysis_id: str | None = None
    latest_analysis_at: datetime | None = None
    classification_category: str | None = None
    nvidia_opportunity_score: int | None = None


class StartupListResponse(BaseModel):
    startups: list[StartupHistoryItem]


class AnalysisHistoryItem(BaseModel):
    analysis_id: str
    status: str
    created_at: datetime
    collected_at: datetime | None = None
    sources_successful: int
    classification_category: str | None = None
    ai_native_score: int | None = None
    wrapper_risk_score: int | None = None
    nvidia_opportunity_score: int | None = None
    gaps_count: int


class StartupAnalysesResponse(BaseModel):
    startup_id: str
    startup_name: str
    analyses: list[AnalysisHistoryItem]


class SavedBriefingResponse(BaseModel):
    analysis_id: str
    startup_name: str
    generated_at: datetime
    markdown: str