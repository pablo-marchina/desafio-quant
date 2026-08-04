from __future__ import annotations

import pytest

from radar.schemas import SearchPlan, SourceCandidate
from radar.scraping.adapters import (
    ExternalProviderDisabledError,
    PlaywrightPageAdapter,
)
from radar.scraping.collectors import SearchBackedCollector
from radar.scraping.provider_factory import build_web_collector
from radar.scraping.provider_preflight import inspect_provider_setup
from radar.settings import RadarSettings


class TestPlaywrightPageAdapterUnit:
    def test_provider_name_is_playwright(self) -> None:
        assert PlaywrightPageAdapter.provider == "playwright"

    def test_fetch_raises_disabled_error_when_external_providers_off(self) -> None:
        adapter = PlaywrightPageAdapter(RadarSettings())
        candidate = SourceCandidate(
            url="https://example.com",
            domain="example.com",
            title="Test",
            source_type="other",
            rank=1,
            provider="test",
        )

        with pytest.raises(ExternalProviderDisabledError) as exc:
            adapter.fetch(candidate)

        assert "playwright" in str(exc.value).lower()


class TestPlaywrightInProviderFactory:
    def test_factory_builds_firecrawl_playwright_stack(self) -> None:
        settings = RadarSettings(search_provider="firecrawl", page_provider="playwright")
        collector = build_web_collector(settings)

        assert isinstance(collector, SearchBackedCollector)

    def test_factory_builds_serpapi_playwright_stack(self) -> None:
        settings = RadarSettings(search_provider="serpapi", page_provider="playwright")
        collector = build_web_collector(settings)

        assert isinstance(collector, SearchBackedCollector)

    def test_firecrawl_playwright_stack_fails_closed(self) -> None:
        settings = RadarSettings(search_provider="firecrawl", page_provider="playwright")
        collector = build_web_collector(settings)

        sources, errors = collector.collect_with_errors(
            SearchPlan(
                query="test",
                keywords=["test"],
                source_types=["other"],
                collection_plan=["configured providers"],
            )
        )

        assert sources == []
        assert len(errors) == 1
        assert errors[0].step == "scraper.search"
        assert errors[0].provider == "firecrawl"
        assert errors[0].error_type == ExternalProviderDisabledError.__name__


class TestPlaywrightInProviderPreflight:
    def test_firecrawl_playwright_is_blocked_when_disabled(self) -> None:
        preflight = inspect_provider_setup(
            RadarSettings(search_provider="firecrawl", page_provider="playwright")
        )

        assert preflight.status == "blocked"
        assert preflight.search_provider == "firecrawl"
        assert preflight.page_provider == "playwright"
        assert preflight.network_required is True
        assert preflight.requires_user_authorization is True

    def test_firecrawl_playwright_reports_missing_credentials(self) -> None:
        preflight = inspect_provider_setup(
            RadarSettings(
                enable_external_providers=True,
                search_provider="firecrawl",
                page_provider="playwright",
            )
        )

        assert preflight.status == "misconfigured"
        assert preflight.network_required is True
        assert "FIRECRAWL_API_KEY" in preflight.missing_credentials

    def test_firecrawl_playwright_ready_with_key(self) -> None:
        preflight = inspect_provider_setup(
            RadarSettings(
                enable_external_providers=True,
                search_provider="firecrawl",
                page_provider="playwright",
                firecrawl_api_key="test-key",
            )
        )

        assert preflight.status == "ready"
        assert preflight.network_required is True

    def test_serpapi_playwright_is_blocked_when_disabled(self) -> None:
        preflight = inspect_provider_setup(
            RadarSettings(search_provider="serpapi", page_provider="playwright")
        )

        assert preflight.status == "blocked"
        assert preflight.search_provider == "serpapi"
        assert preflight.page_provider == "playwright"
