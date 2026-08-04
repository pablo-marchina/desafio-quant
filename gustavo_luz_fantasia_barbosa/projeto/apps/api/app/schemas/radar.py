from pydantic import BaseModel, Field, HttpUrl


class StartupRadarRequest(BaseModel):
    sector: str | None = None
    focus: str | None = None
    stage: str | None = None
    limit: int = Field(default=8, ge=1, le=20)


class StartupRadarToolFit(BaseModel):
    technology: str
    category: str
    fit_percent: int
    source_url: HttpUrl | str
    reason: str


class StartupSourceEvidence(BaseModel):
    kind: str
    label: str
    url: HttpUrl | str
    host: str
    detail: str
    confidence_impact: int


class StartupRadarResult(BaseModel):
    startup_name: str
    sector: str
    stage: str | None = None
    source: str
    website_url: HttpUrl | str | None = None
    github_url: HttpUrl | str | None = None
    source_url: HttpUrl | str | None = None
    opportunity_percent: int
    approach_timing: str = "exploratorio"
    ai_native_score: int
    nvidia_fit_score: int
    wrapper_risk_score: int
    source_confidence: int
    source_summary: str
    source_evidence: list[StartupSourceEvidence]
    top_tools: list[StartupRadarToolFit]
    evidence_summary: str
    signals: list[str]


class StartupRadarResponse(BaseModel):
    source: str
    total_candidates: int
    returned: int
    results: list[StartupRadarResult]


class StartupSearchRequest(BaseModel):
    query: str = Field(..., min_length=2)
    limit: int = Field(default=8, ge=1, le=20)


class StartupSearchResult(BaseModel):
    startup_name: str
    country_code: str | None = None
    sector: str
    stage: str | None = None
    source: str
    website_url: HttpUrl | str | None = None
    github_url: HttpUrl | str | None = None
    source_url: HttpUrl | str | None = None
    description: str
    signals: list[str]
    match_score: int


class StartupSearchResponse(BaseModel):
    query: str
    source: str
    source_path: str
    total_candidates: int
    returned: int
    results: list[StartupSearchResult]


class StartupDiscoveryResult(BaseModel):
    startup_name: str
    country_code: str | None = None
    sector: str
    stage: str | None = None
    source: str
    website_url: HttpUrl | str | None = None
    github_url: HttpUrl | str | None = None
    source_url: HttpUrl | str | None = None
    article_title: str
    article_url: HttpUrl | str
    description: str
    signals: list[str]
    confidence: int
    discovered_at: str
    status: str


class StartupRepertoireResponse(BaseModel):
    source_url: HttpUrl | str
    discovery_path: str
    total: int
    results: list[StartupDiscoveryResult]


class StartupRepertoireRefreshRequest(BaseModel):
    max_items: int = Field(default=20, ge=1, le=50)


class StartupRepertoireRefreshResponse(BaseModel):
    source_url: HttpUrl | str
    found: int
    added: int
    total: int
    results: list[StartupDiscoveryResult]


class StartupRepertoireUseRequest(BaseModel):
    min_confidence: int = Field(default=50, ge=0, le=100)


class StartupRepertoireUseResponse(BaseModel):
    imported: int
    skipped: int
    total_active: int
    results: list[StartupSearchResult]


class StartupRepertoireEnrichRequest(BaseModel):
    max_items: int = Field(default=10, ge=1, le=25)


class StartupRepertoireEnrichResponse(BaseModel):
    processed: int
    enriched: int
    needs_review: int
    failed: int
    results: list[StartupDiscoveryResult]


class StartupRepertoireReviewRequest(BaseModel):
    startup_name: str = Field(..., min_length=2)
    article_url: HttpUrl | str | None = None
    website_url: HttpUrl | str
    sector: str | None = None
    stage: str | None = None
    description: str | None = None
    signals: list[str] = Field(default_factory=list)
    promote: bool = True


class StartupRepertoireReviewResponse(BaseModel):
    promoted: bool
    result: StartupDiscoveryResult
