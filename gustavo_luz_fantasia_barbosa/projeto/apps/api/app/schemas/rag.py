from typing import Any
from pydantic import BaseModel, Field, HttpUrl


class IngestNvidiaRequest(BaseModel):
    reset_collection: bool = False


class IngestNvidiaResponse(BaseModel):
    collection_name: str
    documents: int
    chunks: int


class IngestNvidiaOfficialRequest(BaseModel):
    reset_collection: bool = False
    max_chars_per_source: int = Field(default=12000, ge=1000, le=50000)
    max_chunks_per_source: int = Field(default=6, ge=1, le=20)


class NvidiaOfficialSourceResult(BaseModel):
    product_name: str
    source_url: HttpUrl | str
    status: str
    characters: int
    chunks: int
    error: str | None = None


class IngestNvidiaOfficialResponse(BaseModel):
    collection_name: str
    documents: int
    chunks: int
    collected_at: str
    sources: list[NvidiaOfficialSourceResult]


class NvidiaFreshnessCheckRequest(BaseModel):
    max_sources: int = Field(default=8, ge=1, le=24)
    max_chars_per_source: int = Field(default=12000, ge=1000, le=50000)
    persist_results: bool = True
    reingest_changed: bool = False


class NvidiaFreshnessCheckResult(BaseModel):
    product_name: str
    category: str
    source_url: HttpUrl | str
    checked_at: str
    status: str
    action: str
    local_content_hash: str | None = None
    remote_content_hash: str | None = None
    local_modified_at: str | None = None
    remote_modified_at: str | None = None
    characters: int
    is_useful_for_startups: bool
    usefulness_score: int
    useful_topics: list[str]
    usefulness_reason: str
    error: str | None = None


class NvidiaFreshnessCheckResponse(BaseModel):
    checked: int
    up_to_date: int
    changed: int
    failed: int
    persisted: bool
    reingested: int = 0
    results: list[NvidiaFreshnessCheckResult]


class RagSearchRequest(BaseModel):
    query: str = Field(..., min_length=2)
    limit: int = Field(default=5, ge=1, le=20)
    category: str | None = None


class RagSearchResult(BaseModel):
    score: float
    product_name: str
    category: str
    source_url: HttpUrl | str
    chunk_text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RagSearchResponse(BaseModel):
    query: str
    results: list[RagSearchResult]


class StartupEvidenceSearchRequest(BaseModel):
    query: str = Field(..., min_length=2)
    startup_name: str | None = None
    analysis_run_id: str | None = None
    limit: int = Field(default=5, ge=1, le=20)


class StartupEvidenceSearchResult(BaseModel):
    score: float
    startup_name: str
    analysis_run_id: str
    source_url: HttpUrl | str
    chunk_text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class StartupEvidenceSearchResponse(BaseModel):
    query: str
    results: list[StartupEvidenceSearchResult]


class TechnologySummary(BaseModel):
    product_name: str
    category: str
    source_url: HttpUrl | str
    summary: str
