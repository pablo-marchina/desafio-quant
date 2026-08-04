from pydantic import BaseModel, Field, HttpUrl
from typing import Any


class StartupAnalysisRequest(BaseModel):
    startup_name: str = Field(..., min_length=2)
    website_url: HttpUrl | None = None
    sector: str | None = None
    description: str | None = None
    technical_gaps: list[str] = Field(default_factory=list)
    force_nvidia_update_check: bool = False


class StartupSearchPlan(BaseModel):
    version: str = "search_plan_v1"
    query: str
    search_terms: list[str] = Field(default_factory=list)
    source_priorities: list[str] = Field(default_factory=list)
    evidence_targets: list[str] = Field(default_factory=list)


class StartupRecommendation(BaseModel):
    technology: str
    category: str
    priority: str
    implementation_complexity: str = "medium"
    next_action: str = ""
    technical_reason: str
    business_reason: str
    source_url: HttpUrl | str
    retrieval_score: float
    rerank_details: dict[str, Any] = Field(default_factory=dict)


class StartupSourceSummary(BaseModel):
    source_url: HttpUrl | str
    status: str
    characters: int = 0
    excerpt: str | None = None


class StartupProfileItem(BaseModel):
    value: str
    evidence: str
    source_url: HttpUrl | str | None = None
    confidence: float = 0.0


class StartupStructuredProfile(BaseModel):
    founders: list[StartupProfileItem] = Field(default_factory=list)
    funding: list[StartupProfileItem] = Field(default_factory=list)
    customers: list[StartupProfileItem] = Field(default_factory=list)
    technologies: list[StartupProfileItem] = Field(default_factory=list)
    ai_signals: list[StartupProfileItem] = Field(default_factory=list)


class StartupSourcePage(BaseModel):
    source_url: HttpUrl | str
    title: str | None = None
    source_type: str = "startup_page"
    status_code: int | None = None
    characters: int = 0
    excerpt: str | None = None
    collected_at: str | None = None


class EvidenceCheck(BaseModel):
    claim: str
    support: str
    confidence: float
    source: HttpUrl | str
    note: str
    severity: str = "info"
    blocks_recommendation: bool = False
    claim_type: str = "general"
    evidence_ids: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    recommendation_technology: str | None = None
    minimum_required: str | None = None
    blocking_reason: str | None = None


class PipelineStepTrace(BaseModel):
    name: str
    agent: str
    status: str
    started_at: str
    finished_at: str | None = None
    duration_ms: int | None = None
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class StartupAnalysisResponse(BaseModel):
    analysis_run_id: str | None = None
    startup_name: str
    classification: str
    ai_native_score: int
    wrapper_risk_score: int
    nvidia_fit_score: int
    search_plan: StartupSearchPlan | None = None
    source_summary: StartupSourceSummary | None = None
    source_pages: list[StartupSourcePage] = Field(default_factory=list)
    structured_profile: StartupStructuredProfile = Field(
        default_factory=StartupStructuredProfile
    )
    startup_evidence_chunks: int = 0
    detected_gaps: list[str]
    recommendations: list[StartupRecommendation]
    evidence_checks: list[EvidenceCheck]
    briefing_markdown: str
    quality_metrics: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str]
    pipeline_trace: list[PipelineStepTrace] = Field(default_factory=list)


class AnalysisRunSummary(BaseModel):
    analysis_run_id: str
    startup_name: str
    website_url: HttpUrl | str | None = None
    sector: str | None = None
    classification: str
    ai_native_score: int
    wrapper_risk_score: int
    nvidia_fit_score: int
    recommendations_count: int = 0
    scraped_pages_count: int = 0
    created_at: str


class AnalysisBriefingResponse(BaseModel):
    analysis_run_id: str
    startup_name: str
    created_at: str
    briefing_markdown: str
