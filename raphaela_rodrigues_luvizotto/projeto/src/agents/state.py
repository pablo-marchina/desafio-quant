from __future__ import annotations

from typing import Any, TypedDict

from src.models import (
    Evidence,
    RagResult,
    Recommendation,
    ScrapeRun,
    Startup,
    StartupClassification,
)


class PipelineState(TypedDict, total=False):
    query: str
    target_startup: str | None
    candidate_startups: list[str]
    discovered_urls: list[str]
    raw_documents: list[dict[str, Any]]
    structured_startup: Startup | None
    initial_classification: StartupClassification | None
    validated_evidences: list[Evidence]
    validation_report: dict[str, Any]
    quality_flags: dict[str, Any]
    retry_counts: dict[str, int]
    retry_requested_by: str | None
    scrape_run: ScrapeRun | None
    rag_context: RagResult
    recommendations: list[Recommendation]
    final_briefing: str
    errors: list[str]
    logs: list[str]
