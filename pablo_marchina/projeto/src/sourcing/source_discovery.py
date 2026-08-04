from __future__ import annotations

from urllib.parse import urlparse

from pydantic import BaseModel, Field, HttpUrl

from src.sourcing.source_registry import SourceCategory


class StartupSourceCandidate(BaseModel):
    startup_name: str
    category: SourceCategory
    url: HttpUrl
    discovery_method: str
    priority: float = Field(ge=0.0, le=1.0)


def _candidate(
    *,
    startup_name: str,
    category: SourceCategory,
    url: str,
    discovery_method: str,
    priority: float,
) -> StartupSourceCandidate:
    return StartupSourceCandidate.model_validate(
        {
            "startup_name": startup_name,
            "category": category,
            "url": url,
            "discovery_method": discovery_method,
            "priority": priority,
        }
    )


def discover_seed_sources(startup_name: str, official_url: str) -> list[StartupSourceCandidate]:
    parsed = urlparse(official_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("official_url must be an absolute public URL")
    base = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    slug = _slug(startup_name)
    return [
        _candidate(
            startup_name=startup_name,
            category=SourceCategory.OFFICIAL_SITE,
            url=base,
            discovery_method="provided_official_url",
            priority=1.0,
        ),
        _candidate(
            startup_name=startup_name,
            category=SourceCategory.OFFICIAL_BLOG,
            url=f"{base}/blog",
            discovery_method="deterministic_common_path",
            priority=0.65,
        ),
        _candidate(
            startup_name=startup_name,
            category=SourceCategory.CAREERS,
            url=f"{base}/careers",
            discovery_method="deterministic_common_path",
            priority=0.55,
        ),
        _candidate(
            startup_name=startup_name,
            category=SourceCategory.GITHUB_PUBLIC,
            url=f"https://github.com/{slug}",
            discovery_method="public_profile_guess_requires_validation",
            priority=0.35,
        ),
    ]


def _slug(value: str) -> str:
    chars = [char.lower() if char.isalnum() else "-" for char in value.strip()]
    return "-".join(part for part in "".join(chars).split("-") if part)
