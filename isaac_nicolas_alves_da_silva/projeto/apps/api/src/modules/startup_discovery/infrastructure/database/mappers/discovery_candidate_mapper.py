"""Mapper entre StartupDiscoveryCandidate e DiscoveryCandidateModel."""

from apps.api.src.modules.startup_discovery.domain.entities import (
    StartupDiscoveryCandidate,
)
from apps.api.src.modules.startup_discovery.domain.enums import CandidateStatus
from apps.api.src.modules.startup_discovery.infrastructure.database.models.discovery_candidate_model import (
    DiscoveryCandidateModel,
)


class DiscoveryCandidateMapper:

    @staticmethod
    def to_model(candidate: StartupDiscoveryCandidate) -> DiscoveryCandidateModel:
        return DiscoveryCandidateModel(
            id=candidate.id,
            run_id=candidate.run_id,
            name=candidate.name,
            normalized_name=candidate.normalized_name,
            discovery_source=candidate.discovery_source,
            discovery_source_url=candidate.discovery_source_url,
            category=candidate.category,
            rank=candidate.rank,
            description=candidate.description,
            official_website_url=candidate.official_website_url,
            official_site_confidence=candidate.official_site_confidence,
            enrichment_sources=candidate.enrichment_sources,
            status=candidate.status.value,
            rejection_reason=candidate.rejection_reason,
            url_ingestion_job_id=candidate.url_ingestion_job_id,
            created_at=candidate.created_at,
            updated_at=candidate.updated_at,
        )

    @staticmethod
    def update_model(
        model: DiscoveryCandidateModel,
        candidate: StartupDiscoveryCandidate,
    ) -> None:
        model.name = candidate.name
        model.normalized_name = candidate.normalized_name
        model.category = candidate.category
        model.rank = candidate.rank
        model.description = candidate.description
        model.official_website_url = candidate.official_website_url
        model.official_site_confidence = candidate.official_site_confidence
        model.enrichment_sources = candidate.enrichment_sources
        model.status = candidate.status.value
        model.rejection_reason = candidate.rejection_reason
        model.url_ingestion_job_id = candidate.url_ingestion_job_id
        model.updated_at = candidate.updated_at

    @staticmethod
    def to_entity(model: DiscoveryCandidateModel) -> StartupDiscoveryCandidate:
        return StartupDiscoveryCandidate(
            id=model.id,
            run_id=model.run_id,
            name=model.name,
            normalized_name=model.normalized_name,
            discovery_source=model.discovery_source,
            discovery_source_url=model.discovery_source_url,
            category=model.category,
            rank=model.rank,
            description=model.description,
            official_website_url=model.official_website_url,
            official_site_confidence=model.official_site_confidence,
            enrichment_sources=list(model.enrichment_sources or []),
            status=CandidateStatus(model.status),
            rejection_reason=model.rejection_reason,
            url_ingestion_job_id=model.url_ingestion_job_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
