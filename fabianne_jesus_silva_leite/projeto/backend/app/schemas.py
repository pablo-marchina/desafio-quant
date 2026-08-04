from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl

class CollectRequest(BaseModel):
    startup_name: str = Field(min_length=2, max_length=120)
    url: HttpUrl


class SourceMetadata(BaseModel):
    url: str
    title: str | None
    extraction_method: str


class CollectResponse(BaseModel):
    startup_name: str
    source: SourceMetadata
    collected_at: datetime
    text_characters: int
    word_count: int
    clean_text: str


class Evidence(BaseModel):
    claim: str
    quote: str
    source_url: str
    status: str
    confidence: float
    category: str


class ScoreReason(BaseModel):
    criterion: str
    points: int
    reason: str


class ClassificationResult(BaseModel):
    category: str
    ai_native_score: int
    wrapper_risk_score: int
    nvidia_opportunity_score: int
    score_reasons: list[ScoreReason]


class AnalyzeResponse(BaseModel):
    startup_name: str
    source: SourceMetadata
    collected_at: datetime
    classification: ClassificationResult
    evidences: list[Evidence]
    ai_signals_found: list[str]
    clean_text_preview: str

class AnalyzeMultipleRequest(BaseModel):
    startup_name: str = Field(min_length=2, max_length=120)
    urls: list[HttpUrl] = Field(min_length=1, max_length=6)


class SourceCollectionStatus(BaseModel):
    url: str
    status: str
    title: str | None = None
    extraction_method: str | None = None
    text_characters: int = 0
    word_count: int = 0
    error: str | None = None

class AnalyzeMultipleResponse(BaseModel):
    startup_name: str
    collected_at: datetime
    sources: list[SourceCollectionStatus]
    sources_successful: int
    sources_failed: int
    classification: ClassificationResult
    evidences: list[Evidence]
    ai_signals_found: list[str]
    clean_text_preview: str

class DiscoverSourcesRequest(BaseModel):
    startup_name: str = Field(min_length=2, max_length=120)
    sector: str | None = Field(default=None, max_length=80)
    official_url: HttpUrl | None = None
    max_sources: int = Field(default=5, ge=3, le=6)


class DiscoveredSource(BaseModel):
    url: str
    title: str
    snippet: str | None = None
    source_type: str
    tier: int
    priority: int
    reason: str
    search_query: str | None = None

class DiscoverSourcesResponse(BaseModel):
    startup_name: str
    queries_used: list[str]
    sources: list[DiscoveredSource]
    sources_found: int

class ResearchRequest(BaseModel):
    startup_name: str = Field(min_length=2, max_length=120)
    sector: str | None = Field(default=None, max_length=80)
    official_url: HttpUrl | None = None
    max_sources: int = Field(default=5, ge=3, le=6)


class ExcludedSource(BaseModel):
    url: str
    title: str
    source_type: str
    reason: str
    search_query: str | None = None

class EvidenceValidationReport(BaseModel):
    total_received: int
    valid_count: int
    duplicate_count: int
    invalid_count: int
    invalid_reasons: list[str]


class StartupProfile(BaseModel):
    ai_product: list[Evidence]
    workflow_depth: list[Evidence]
    proprietary_data: list[Evidence]
    governance_security: list[Evidence]
    scale_traction: list[Evidence]
    model_and_serving: list[Evidence]


class Gap(BaseModel):
    category: str
    status: str
    message: str

class ResearchResponse(BaseModel):
    startup_name: str
    queries_used: list[str]
    candidate_sources: list[DiscoveredSource]
    selected_sources: list[DiscoveredSource]
    excluded_sources: list[ExcludedSource]
    collected_at: datetime
    sources: list[SourceCollectionStatus]
    sources_successful: int
    sources_failed: int
    classification: ClassificationResult
    evidences: list[Evidence]
    evidence_validation: EvidenceValidationReport
    profile: StartupProfile
    gaps: list[Gap]
    ai_signals_found: list[str]
    clean_text_preview: str