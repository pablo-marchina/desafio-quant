"""Entidades do modulo startup_discovery."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

from apps.api.src.modules.startup_discovery.domain.enums import (
    CandidateStatus,
    DiscoveryRunStatus,
)
from apps.api.src.modules.startup_discovery.domain.exceptions import (
    InvalidCandidateTransitionError,
    InvalidDiscoveryRunTransitionError,
)


class DiscoveryRun:
    """Representa uma execucao de descoberta de startups em hubs publicos."""

    def __init__(
        self,
        *,
        id: UUID | None = None,
        status: DiscoveryRunStatus = DiscoveryRunStatus.PENDING,
        hubs_processed: int = 0,
        urls_found: int = 0,
        jobs_submitted: int = 0,
        candidates_discovered: int = 0,
        candidates_enriched: int = 0,
        error_message: str | None = None,
        created_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        self.id: UUID = id or uuid4()
        self.status = status
        self.hubs_processed = hubs_processed
        self.urls_found = urls_found
        self.jobs_submitted = jobs_submitted
        self.candidates_discovered = candidates_discovered
        self.candidates_enriched = candidates_enriched
        self.error_message = error_message
        self.created_at: datetime = created_at or datetime.now(timezone.utc)
        self.completed_at = completed_at

    def start(self) -> None:
        if self.status is not DiscoveryRunStatus.PENDING:
            raise InvalidDiscoveryRunTransitionError(
                f"Nao e possivel iniciar um DiscoveryRun em status {self.status.value}."
            )
        self.status = DiscoveryRunStatus.RUNNING

    def complete(
        self,
        *,
        hubs_processed: int,
        urls_found: int,
        jobs_submitted: int,
        candidates_discovered: int = 0,
        candidates_enriched: int = 0,
    ) -> None:
        if self.status is not DiscoveryRunStatus.RUNNING:
            raise InvalidDiscoveryRunTransitionError(
                f"Nao e possivel completar um DiscoveryRun em status {self.status.value}."
            )
        self.status = DiscoveryRunStatus.COMPLETED
        self.hubs_processed = hubs_processed
        self.urls_found = urls_found
        self.jobs_submitted = jobs_submitted
        self.candidates_discovered = candidates_discovered
        self.candidates_enriched = candidates_enriched
        self.completed_at = datetime.now(timezone.utc)

    def fail(self, reason: str) -> None:
        if self.status is not DiscoveryRunStatus.RUNNING:
            raise InvalidDiscoveryRunTransitionError(
                f"Nao e possivel falhar um DiscoveryRun em status {self.status.value}."
            )
        self.status = DiscoveryRunStatus.FAILED
        self.error_message = reason
        self.completed_at = datetime.now(timezone.utc)


@dataclass
class DiscoverySubmission:
    """Candidato descoberto que foi submetido ao pipeline de analise."""

    run_id: UUID
    hub_name: str
    website_url: str
    job_id: UUID
    name: str | None = None
    hub_profile_url: str | None = None
    short_description: str | None = None
    declared_sector: str | None = None
    id: UUID = field(default_factory=uuid4)
    submitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class StartupDiscoveryCandidate:
    """Startup descoberta por nome em um hub — aguarda enriquecimento para obter URL oficial."""

    def __init__(
        self,
        *,
        id: UUID | None = None,
        run_id: UUID,
        name: str,
        normalized_name: str,
        discovery_source: str,
        discovery_source_url: str,
        category: str | None = None,
        rank: int | None = None,
        description: str | None = None,
        official_website_url: str | None = None,
        official_site_confidence: float | None = None,
        enrichment_sources: list[str] | None = None,
        status: CandidateStatus = CandidateStatus.DISCOVERED,
        rejection_reason: str | None = None,
        url_ingestion_job_id: UUID | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        self.id: UUID = id or uuid4()
        self.run_id = run_id
        self.name = name
        self.normalized_name = normalized_name
        self.discovery_source = discovery_source
        self.discovery_source_url = discovery_source_url
        self.category = category
        self.rank = rank
        self.description = description
        self.official_website_url = official_website_url
        self.official_site_confidence = official_site_confidence
        self.enrichment_sources: list[str] = enrichment_sources or []
        self.status = status
        self.rejection_reason = rejection_reason
        self.url_ingestion_job_id = url_ingestion_job_id
        now = datetime.now(timezone.utc)
        self.created_at: datetime = created_at or now
        self.updated_at: datetime = updated_at or now

    def enrich(
        self,
        *,
        official_website_url: str,
        official_site_confidence: float,
        enrichment_sources: list[str],
    ) -> None:
        if self.status not in (CandidateStatus.DISCOVERED, CandidateStatus.ENRICHED):
            raise InvalidCandidateTransitionError(
                f"Candidato em status {self.status.value} nao pode ser enriquecido."
            )
        self.official_website_url = official_website_url
        self.official_site_confidence = official_site_confidence
        self.enrichment_sources = enrichment_sources
        self.status = CandidateStatus.ENRICHED
        self.updated_at = datetime.now(timezone.utc)

    def mark_submitted(self, job_id: UUID) -> None:
        if self.status is not CandidateStatus.ENRICHED:
            raise InvalidCandidateTransitionError(
                f"Candidato em status {self.status.value} nao pode ser submetido."
            )
        self.url_ingestion_job_id = job_id
        self.status = CandidateStatus.SUBMITTED
        self.updated_at = datetime.now(timezone.utc)

    def reject(self, reason: str) -> None:
        if self.status not in (CandidateStatus.DISCOVERED, CandidateStatus.ENRICHED):
            raise InvalidCandidateTransitionError(
                f"Candidato em status {self.status.value} nao pode ser rejeitado."
            )
        self.rejection_reason = reason
        self.status = CandidateStatus.REJECTED
        self.updated_at = datetime.now(timezone.utc)

    def fail(self, reason: str) -> None:
        self.rejection_reason = reason
        self.status = CandidateStatus.FAILED
        self.updated_at = datetime.now(timezone.utc)
