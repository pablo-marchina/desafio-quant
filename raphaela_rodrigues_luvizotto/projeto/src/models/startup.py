from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Evidence(BaseModel):
    id: str | None = None
    startup_name: str | None = None
    url: str
    title: str | None = None
    source_type: str
    excerpt: str | None = None
    content: str | None = None
    collected_at: str = Field(default_factory=_utc_now)
    method: str = "requests_bs4"
    http_status: int | None = None
    is_validated: bool = False
    relevance_score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class StartupClassification(BaseModel):
    label: str = "unknown"
    score: float | None = None
    rationale: str | None = None
    method: str = "heuristic_stub"
    signals: list[str] = Field(default_factory=list)


class Startup(BaseModel):
    id: str | None = None
    name: str
    canonical_url: str | None = None
    segment: str | None = None
    short_description: str | None = None
    country: str | None = "Brazil"
    city: str | None = None
    ai_native_score: float | None = None
    classification: StartupClassification | None = None
    tags: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_utc_now)
    updated_at: str = Field(default_factory=_utc_now)


class ScrapeRun(BaseModel):
    id: str | None = None
    query: str
    startup_name: str | None = None
    status: str = "pending"
    urls_requested: list[str] = Field(default_factory=list)
    documents_collected: int = 0
    raw_artifact_dir: str | None = None
    started_at: str = Field(default_factory=_utc_now)
    finished_at: str | None = None
    errors: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Recommendation(BaseModel):
    startup_name: str
    recommendation_type: str = "nvidia_fit"
    summary: str
    rationale: str
    matched_products: list[str] = Field(default_factory=list)
    matched_context_snippets: list[str] = Field(default_factory=list)
    confidence: float | None = None
    next_steps: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RagCitationItem(BaseModel):
    citation: str
    snippet: str
    source_title: str | None = None
    source_url: str | None = None
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    retrieval_score: float | None = None
    rerank_score: float | None = None
    document_id: str | None = None


class RagResult(BaseModel):
    query: str
    summary: str = ""
    items: list[RagCitationItem] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
