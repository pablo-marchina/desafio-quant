"""Schemas Pydantic da presentation layer do modulo startup_discovery."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from apps.api.src.modules.startup_discovery.domain.enums import (
    CandidateStatus,
    DiscoveryRunStatus,
)


class SubmittedUrlResponse(BaseModel):
    hub_name: str
    url: str
    job_id: UUID
    name: str | None = None
    hub_profile_url: str | None = None
    short_description: str | None = None
    declared_sector: str | None = None


class DiscoveryRunResponse(BaseModel):
    id: UUID
    status: DiscoveryRunStatus
    hubs_processed: int
    urls_found: int
    jobs_submitted: int
    candidates_discovered: int = 0
    candidates_enriched: int = 0
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
    submitted_urls: list[SubmittedUrlResponse] = []


class CandidateResponse(BaseModel):
    id: UUID
    run_id: UUID
    name: str
    normalized_name: str
    discovery_source: str
    category: str | None
    rank: int | None
    description: str | None
    official_website_url: str | None
    official_site_confidence: float | None
    enrichment_sources: list[str]
    status: CandidateStatus
    rejection_reason: str | None
    url_ingestion_job_id: UUID | None
    created_at: datetime
    updated_at: datetime


class CandidateListResponse(BaseModel):
    run_id: UUID
    total: int
    candidates: list[CandidateResponse]
