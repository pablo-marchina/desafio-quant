"""Mapper entre DiscoverySubmission e DiscoverySubmissionModel."""

from apps.api.src.modules.startup_discovery.domain.entities import DiscoverySubmission
from apps.api.src.modules.startup_discovery.infrastructure.database.models.discovery_submission_model import (
    DiscoverySubmissionModel,
)


class DiscoverySubmissionMapper:

    @staticmethod
    def to_model(submission: DiscoverySubmission) -> DiscoverySubmissionModel:
        return DiscoverySubmissionModel(
            id=submission.id,
            run_id=submission.run_id,
            hub_name=submission.hub_name,
            website_url=submission.website_url,
            job_id=submission.job_id,
            name=submission.name,
            hub_profile_url=submission.hub_profile_url,
            short_description=submission.short_description,
            declared_sector=submission.declared_sector,
            submitted_at=submission.submitted_at,
        )

    @staticmethod
    def update_model(
        model: DiscoverySubmissionModel,
        submission: DiscoverySubmission,
    ) -> None:
        model.run_id = submission.run_id
        model.hub_name = submission.hub_name
        model.website_url = submission.website_url
        model.job_id = submission.job_id
        model.name = submission.name
        model.hub_profile_url = submission.hub_profile_url
        model.short_description = submission.short_description
        model.declared_sector = submission.declared_sector
        model.submitted_at = submission.submitted_at

    @staticmethod
    def to_entity(model: DiscoverySubmissionModel) -> DiscoverySubmission:
        return DiscoverySubmission(
            id=model.id,
            run_id=model.run_id,
            hub_name=model.hub_name,
            website_url=model.website_url,
            job_id=model.job_id,
            name=model.name,
            hub_profile_url=model.hub_profile_url,
            short_description=model.short_description,
            declared_sector=model.declared_sector,
            submitted_at=model.submitted_at,
        )
