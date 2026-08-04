from pydantic import BaseModel, Field


class NvidiaTechnologyResponse(BaseModel):
    name: str
    category: str
    description: str
    source_url: str


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=20)


class KnowledgeSearchResultResponse(BaseModel):
    name: str
    category: str
    description: str
    source_url: str
    score: float
    matched_keywords: tuple[str, ...]


class KnowledgeIngestResponse(BaseModel):
    status: str
    document_count: int
    chunk_count: int


class SourceDocumentPreviewResponse(BaseModel):
    url: str
    source_type: str
    title: str | None = None
    extracted_text: str | None = None
    scrape_status: str
    scrape_error: str | None = None


class LiveSearchLinkResponse(BaseModel):
    label: str
    url: str


class MarketCandidateResponse(BaseModel):
    name: str
    sector: str
    website: str
    why_relevant: str
    ai_native_signals: tuple[str, ...]
    nvidia_opportunity: tuple[str, ...]
    wrapper_risk: float
    nvidia_fit: float
    urgency: float
    rank_score: float
    evidence_count: int
    source_urls: tuple[str, ...]
    analysis_text: str


class MarketDiscoveryRequest(BaseModel):
    query: str = Field(min_length=1)
    country: str = "Brasil"
    max_results: int = Field(default=10, ge=1, le=50)


class MarketDiscoveryResponse(BaseModel):
    status: str
    run_type: str
    query: str
    country: str
    max_results: int
    summary: str
    trend_signals: tuple[str, ...]
    suggested_queries: tuple[str, ...]
    source_targets: tuple[str, ...]
    live_search_links: tuple[LiveSearchLinkResponse, ...]
    candidates: tuple[MarketCandidateResponse, ...]
    evaluation_checklist: tuple[str, ...]
    next_actions: tuple[str, ...]
    crawl_status: str
    crawled_source_count: int


class EvidenceClaimResponse(BaseModel):
    claim: str
    claim_type: str
    supporting_text: str
    confidence: float
    validation_status: str


class StartupProfileDraftResponse(BaseModel):
    name: str | None
    website: str
    description: str | None
    ai_usage_summary: str | None
    sectors: tuple[str, ...]
    technology_signals: tuple[str, ...]
    evidence_claims: tuple[EvidenceClaimResponse, ...]
    accepted_claims: tuple[EvidenceClaimResponse, ...]
    review_claims: tuple[EvidenceClaimResponse, ...]
    persisted: "PersistedStartupAnalysisResponse | None" = None


class StartupProfileExtractionRequest(BaseModel):
    url: str = Field(min_length=1)
    title: str | None = None
    extracted_text: str = Field(min_length=1)
    persist: bool = False


class PersistedStartupAnalysisResponse(BaseModel):
    startup_id: str
    source_document_id: str
    evidence_claim_ids: tuple[str, ...]
    technology_signal_ids: tuple[str, ...]


class AiMaturityClassificationRequest(BaseModel):
    url: str = Field(min_length=1)
    title: str | None = None
    extracted_text: str = Field(min_length=1)
    persist: bool = False
    startup_id: str | None = None


class PersistedAssessmentResponse(BaseModel):
    assessment_id: str


class AiMaturityAssessmentResponse(BaseModel):
    label: str
    confidence: float
    explanation: str
    scores: dict[str, float]
    persisted: PersistedAssessmentResponse | None = None


class GapDiagnosisRequest(BaseModel):
    url: str = Field(min_length=1)
    title: str | None = None
    extracted_text: str = Field(min_length=1)


class GapDiagnosisResponse(BaseModel):
    gap_type: str
    priority: str
    confidence: float
    evidence_basis: str
    rationale: str
    suggested_action: str


class GapDiagnosisReportResponse(BaseModel):
    summary: str
    gaps: tuple[GapDiagnosisResponse, ...]


class RecommendationRequest(BaseModel):
    url: str = Field(min_length=1)
    title: str | None = None
    extracted_text: str = Field(min_length=1)


class TechnologyRecommendationResponse(BaseModel):
    gap_type: str
    technology_name: str
    source_url: str
    priority: str
    complexity: str
    technical_rationale: str
    business_rationale: str
    next_action: str


class RecommendationReportResponse(BaseModel):
    summary: str
    recommendations: tuple[TechnologyRecommendationResponse, ...]


class BriefingGenerationRequest(BaseModel):
    url: str = Field(min_length=1)
    title: str | None = None
    extracted_text: str = Field(min_length=1)
    persist: bool = False
    startup_id: str | None = None


class PersistedBriefingResponse(BaseModel):
    briefing_id: str


class BriefingGenerationResponse(BaseModel):
    title: str
    markdown: str
    source_urls: tuple[str, ...]
    persisted: PersistedBriefingResponse | None = None


class BriefingReadResponse(BaseModel):
    id: str
    startup_id: str
    title: str
    markdown: str
    source_urls: tuple[str, ...]


class BriefingExportResponse(BaseModel):
    id: str
    format: str
    filename: str
    content: str


class EmailReportRequest(BaseModel):
    to_email: str = Field(min_length=3)
    subject: str = Field(min_length=1)
    markdown: str = Field(min_length=1)


class EmailReportResponse(BaseModel):
    status: str
    detail: str


class RadarRequest(BaseModel):
    url: str = Field(min_length=1)
    title: str | None = None
    extracted_text: str = Field(min_length=1)


class RadarResponse(BaseModel):
    wrapper_risk: float
    defensibility: float
    nvidia_fit: float
    outreach_urgency: float
    summary: str
    recommended_focus: tuple[str, ...]
