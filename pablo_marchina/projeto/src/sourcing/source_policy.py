from __future__ import annotations

from pydantic import BaseModel, Field

from src.scraping.rate_limit_policy import get_available_capabilities, get_rate_limit_policy
from src.sourcing.source_registry import SourceCategory


class SourcePolicy(BaseModel):
    category: SourceCategory
    robots_required: bool = True
    tos_required: bool = True
    public_only: bool = True
    allow_authenticated_scraping: bool = False
    rate_limit_per_minute: int = Field(default=6, ge=1)
    user_agent_required: bool = True
    blocked_means_failed: bool = True


def policy_for_category(category: SourceCategory) -> SourcePolicy:
    """Return a SourcePolicy for a given category.

    Consults the scraping engine's rate-limit policies when available.
    """
    if category in {SourceCategory.NVIDIA_OFFICIAL, SourceCategory.NVIDIA_DOCS, SourceCategory.CASE_MATERIAL}:
        base_rps = 12
    elif category in {SourceCategory.LINKEDIN_PUBLIC, SourceCategory.GITHUB_PUBLIC}:
        base_rps = 3
    else:
        base_rps = 6

    # Cross-reference with scraping engine policies for consistency
    policy_id = _category_to_policy_id(category)
    scraping_policy = get_rate_limit_policy(policy_id)
    if scraping_policy is not None:
        effective_rps = int(min(base_rps, scraping_policy.requests_per_second * 60))
        base_rps = max(effective_rps, 1)

    return SourcePolicy(category=category, rate_limit_per_minute=base_rps)


def _category_to_policy_id(category: SourceCategory) -> str:
    mapping = {
        SourceCategory.NVIDIA_OFFICIAL: "nvidia_eco",
        SourceCategory.NVIDIA_DOCS: "nvidia_eco",
        SourceCategory.CASE_MATERIAL: "default_polite",
        SourceCategory.LINKEDIN_PUBLIC: "default_polite",
        SourceCategory.GITHUB_PUBLIC: "github_api",
        SourceCategory.TRUSTED_NEWS: "news_site",
        SourceCategory.STARTUP_DIRECTORY: "directory_listing",
        SourceCategory.INVESTOR_PORTFOLIO: "directory_listing",
        SourceCategory.ACCELERATOR: "directory_listing",
    }
    return mapping.get(category, "default_polite")
