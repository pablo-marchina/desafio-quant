"""DTOs do modulo startup_discovery."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from apps.api.src.modules.startup_discovery.domain.enums import (
    CandidateStatus,
    DiscoveryRunStatus,
)


@dataclass(frozen=True)
class StartupCandidate:
    """Startup descoberta em um hub (modo URL) antes da analise semantica."""

    website_url: str
    name: str | None = None
    hub_profile_url: str | None = None
    short_description: str | None = None
    declared_sector: str | None = None


@dataclass(frozen=True)
class DiscoveredCandidateItem:
    """Startup descoberta por nome em hub modo 'name' — sem URL oficial ainda."""

    name: str
    category: str | None = None
    rank: int | None = None
    description: str | None = None


@dataclass(frozen=True)
class SubmittedUrlView:
    hub_name: str
    url: str
    job_id: UUID
    name: str | None = None
    hub_profile_url: str | None = None
    short_description: str | None = None
    declared_sector: str | None = None


@dataclass(frozen=True)
class CandidateView:
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


@dataclass(frozen=True)
class DiscoveryRunView:
    id: UUID
    status: DiscoveryRunStatus
    hubs_processed: int
    urls_found: int
    jobs_submitted: int
    candidates_discovered: int
    candidates_enriched: int
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
    submitted_urls: list[SubmittedUrlView] = field(default_factory=list)
