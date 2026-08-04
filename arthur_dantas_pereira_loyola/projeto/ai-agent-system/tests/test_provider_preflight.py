from __future__ import annotations

from radar.scraping.provider_preflight import inspect_provider_setup
from radar.settings import RadarSettings


def test_fixture_provider_stack_is_ready_without_network() -> None:
    preflight = inspect_provider_setup(RadarSettings())

    assert preflight.status == "ready"
    assert preflight.search_provider == "fixture"
    assert preflight.page_provider == "fixture"
    assert preflight.network_required is False
    assert preflight.can_collect_without_network is True
    assert preflight.missing_credentials == ()


def test_external_provider_stack_is_blocked_until_user_authorizes_it() -> None:
    preflight = inspect_provider_setup(
        RadarSettings(search_provider="serpapi", page_provider="firecrawl")
    )

    assert preflight.status == "blocked"
    assert preflight.network_required is True
    assert preflight.external_providers_enabled is False
    assert preflight.requires_user_authorization is True
    assert preflight.missing_credentials == ("SERPAPI_API_KEY", "FIRECRAWL_API_KEY")
    assert "RADAR_ENABLE_EXTERNAL_PROVIDERS=false" in preflight.messages[0]


def test_external_provider_stack_reports_missing_credentials_when_enabled() -> None:
    preflight = inspect_provider_setup(
        RadarSettings(
            enable_external_providers=True,
            search_provider="serpapi",
            page_provider="firecrawl",
            serpapi_api_key="test-serpapi-key",
        )
    )

    assert preflight.status == "misconfigured"
    assert preflight.network_required is True
    assert preflight.external_providers_enabled is True
    assert preflight.missing_credentials == ("FIRECRAWL_API_KEY",)


def test_external_provider_stack_can_be_ready_but_still_requires_network() -> None:
    preflight = inspect_provider_setup(
        RadarSettings(
            enable_external_providers=True,
            search_provider="serpapi",
            page_provider="firecrawl",
            serpapi_api_key="test-serpapi-key",
            firecrawl_api_key="test-firecrawl-key",
        )
    )

    assert preflight.status == "ready"
    assert preflight.network_required is True
    assert preflight.can_collect_without_network is False
    assert preflight.missing_credentials == ()


def test_mixed_provider_stack_is_misconfigured() -> None:
    preflight = inspect_provider_setup(
        RadarSettings(search_provider="serpapi", page_provider="fixture")
    )

    assert preflight.status == "misconfigured"
    assert preflight.search_provider == "serpapi"
    assert preflight.page_provider == "fixture"
    assert preflight.network_required is True
    assert "Unsupported provider combination" in preflight.messages[0]


def test_firecrawl_firecrawl_stack_is_blocked_until_user_authorizes() -> None:
    preflight = inspect_provider_setup(
        RadarSettings(search_provider="firecrawl", page_provider="firecrawl")
    )

    assert preflight.status == "blocked"
    assert preflight.network_required is True
    assert preflight.external_providers_enabled is False
    assert preflight.requires_user_authorization is True
    assert preflight.missing_credentials == ("FIRECRAWL_API_KEY",)


def test_firecrawl_firecrawl_stack_ready_when_authorized_with_key() -> None:
    preflight = inspect_provider_setup(
        RadarSettings(
            enable_external_providers=True,
            search_provider="firecrawl",
            page_provider="firecrawl",
            firecrawl_api_key="test-firecrawl-key",
        )
    )

    assert preflight.status == "ready"
    assert preflight.network_required is True
    assert preflight.can_collect_without_network is False
    assert preflight.missing_credentials == ()
