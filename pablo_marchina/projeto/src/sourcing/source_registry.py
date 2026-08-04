from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from src.scraping.source_registry import SourceRecord as ScrapingSourceRecord


class SourceCategory(str, Enum):
    OFFICIAL_SITE = "official_site"
    OFFICIAL_BLOG = "official_blog"
    CAREERS = "careers"
    PRODUCT_DOCS = "product_docs"
    LINKEDIN_PUBLIC = "linkedin_public"
    GITHUB_PUBLIC = "github_public"
    TRUSTED_NEWS = "trusted_news"
    ACCELERATOR = "accelerator"
    STARTUP_DIRECTORY = "startup_directory"
    INVESTOR_PORTFOLIO = "investor_portfolio"
    NVIDIA_OFFICIAL = "nvidia_official"
    NVIDIA_DOCS = "nvidia_docs"
    CASE_MATERIAL = "case_material"


class SourceRecord(ScrapingSourceRecord):
    """Unified source record — extends the scraping layer with sourcing metadata."""

    category: SourceCategory = SourceCategory.OFFICIAL_SITE
    authority_weight: float = 0.5
    expected_for_startup_analysis: bool = True
    requires_public_access_check: bool = True
    rate_limit_per_minute: int = Field(default=6, ge=1)


def _scraping_to_sourcing(src: ScrapingSourceRecord, *, category: SourceCategory | None = None) -> SourceRecord:
    """Upgrade a scraping SourceRecord to a sourcing SourceRecord."""
    return SourceRecord(
        **src.model_dump(),
        category=category or SourceCategory.OFFICIAL_SITE,
    )


def default_source_registry() -> list[SourceRecord]:
    return [
        SourceRecord(
            source_id="official_site",
            source_name="Startup official site",
            source_category="official_website",
            base_url="",
            category=SourceCategory.OFFICIAL_SITE,
            authority_weight=1.0,
            collector_type="http",
        ),
        SourceRecord(
            source_id="official_blog",
            source_name="Startup official blog",
            source_category="official_website",
            base_url="",
            category=SourceCategory.OFFICIAL_BLOG,
            authority_weight=0.9,
            collector_type="http",
        ),
        SourceRecord(
            source_id="careers",
            source_name="Startup careers page",
            source_category="jobs",
            base_url="",
            category=SourceCategory.CAREERS,
            authority_weight=0.75,
            collector_type="http",
        ),
        SourceRecord(
            source_id="product_docs",
            source_name="Product or technical docs",
            source_category="technical_docs",
            base_url="",
            category=SourceCategory.PRODUCT_DOCS,
            authority_weight=0.85,
            collector_type="http",
        ),
        SourceRecord(
            source_id="linkedin_public",
            source_name="Allowed public LinkedIn page",
            source_category="official_website",
            base_url="",
            category=SourceCategory.LINKEDIN_PUBLIC,
            authority_weight=0.7,
            collector_type="http",
        ),
        SourceRecord(
            source_id="github_public",
            source_name="Allowed public GitHub profile",
            source_category="github_or_code",
            base_url="",
            category=SourceCategory.GITHUB_PUBLIC,
            authority_weight=0.7,
            collector_type="http",
        ),
        SourceRecord(
            source_id="trusted_news",
            source_name="Trusted news",
            source_category="funding_news",
            base_url="",
            category=SourceCategory.TRUSTED_NEWS,
            authority_weight=0.65,
            collector_type="http",
        ),
        SourceRecord(
            source_id="accelerator",
            source_name="Accelerator profile",
            source_category="ecosystem_directory",
            base_url="",
            category=SourceCategory.ACCELERATOR,
            authority_weight=0.65,
            collector_type="http",
        ),
        SourceRecord(
            source_id="startup_directory",
            source_name="Startup directory",
            source_category="ecosystem_directory",
            base_url="",
            category=SourceCategory.STARTUP_DIRECTORY,
            authority_weight=0.55,
            collector_type="http",
        ),
        SourceRecord(
            source_id="investor_portfolio",
            source_name="Investor or portfolio page",
            source_category="ecosystem_directory",
            base_url="",
            category=SourceCategory.INVESTOR_PORTFOLIO,
            authority_weight=0.75,
            collector_type="http",
        ),
        SourceRecord(
            source_id="nvidia_official",
            source_name="NVIDIA official product page",
            source_category="nvidia_or_partner_ecosystem",
            base_url="",
            category=SourceCategory.NVIDIA_OFFICIAL,
            authority_weight=1.0,
            collector_type="http",
        ),
        SourceRecord(
            source_id="nvidia_docs",
            source_name="NVIDIA documentation",
            source_category="nvidia_or_partner_ecosystem",
            base_url="",
            category=SourceCategory.NVIDIA_DOCS,
            authority_weight=1.0,
            collector_type="http",
        ),
        SourceRecord(
            source_id="case_material",
            source_name="Case material",
            source_category="nvidia_or_partner_ecosystem",
            base_url="",
            category=SourceCategory.CASE_MATERIAL,
            authority_weight=0.8,
            collector_type="http",
        ),
    ]
