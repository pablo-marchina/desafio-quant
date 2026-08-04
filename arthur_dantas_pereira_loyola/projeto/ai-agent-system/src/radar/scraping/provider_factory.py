from __future__ import annotations

from radar.scraping.adapters import (
    DuckDuckGoSearchAdapter,
    FirecrawlPageAdapter,
    FirecrawlSearchAdapter,
    PlaywrightPageAdapter,
)
from radar.scraping.collectors import SearchBackedCollector, StaticSeedCollector, WebCollector
from radar.settings import RadarSettings, get_settings


class ProviderSelectionError(ValueError):
    """Raised when provider settings describe an unsupported collector setup."""


def build_web_collector(settings: RadarSettings | None = None) -> WebCollector:
    """Build the collector selected by settings without performing network calls."""

    active_settings = settings or get_settings()
    if _uses_fixture_stack(active_settings):
        return StaticSeedCollector()

    page_adapter = _build_page_adapter(active_settings)

    if active_settings.search_provider == "firecrawl":
        return SearchBackedCollector(
            search_provider=FirecrawlSearchAdapter(settings=active_settings),
            page_provider=page_adapter,
        )

    if active_settings.search_provider == "serpapi":
        from radar.scraping.adapters import ConfiguredSerpApiSearchAdapter

        return SearchBackedCollector(
            search_provider=ConfiguredSerpApiSearchAdapter(settings=active_settings),
            page_provider=page_adapter,
        )

    if active_settings.search_provider == "duckduckgo":
        return SearchBackedCollector(
            search_provider=DuckDuckGoSearchAdapter(),
            page_provider=page_adapter,
        )

    raise ProviderSelectionError(
        "Unsupported provider combination: "
        f"search_provider={active_settings.search_provider}, "
        f"page_provider={active_settings.page_provider}. "
        "Use fixture/fixture for offline tests, firecrawl, duckduckgo, or serpapi for search, "
        "and firecrawl or playwright for page collection."
    )


def _build_page_adapter(settings: RadarSettings):
    if settings.page_provider == "firecrawl":
        return FirecrawlPageAdapter(settings=settings)
    if settings.page_provider == "playwright":
        from radar.scraping.playwright_pool import warmup_pool

        warmup_pool()
        return PlaywrightPageAdapter(settings=settings)
    raise ProviderSelectionError(
        f"Unsupported page provider: {settings.page_provider}. "
        "Use firecrawl or playwright for external page collection, or fixture/fixture for offline."
    )


def _uses_fixture_stack(settings: RadarSettings) -> bool:
    return settings.search_provider == "fixture" and settings.page_provider == "fixture"
