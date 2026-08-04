from __future__ import annotations

from radar.schemas import SearchPlan
from radar.scraping.adapters import ExternalProviderDisabledError
from radar.scraping.collectors import SearchBackedCollector, StaticSeedCollector
from radar.scraping.provider_factory import ProviderSelectionError, build_web_collector
from radar.settings import RadarSettings


def test_provider_factory_uses_static_seed_collector_by_default() -> None:
    collector = build_web_collector(RadarSettings())

    assert isinstance(collector, StaticSeedCollector)


def test_provider_factory_builds_serpapi_stack_without_network_call() -> None:
    settings = RadarSettings(search_provider="serpapi", page_provider="firecrawl")
    collector = build_web_collector(settings)

    assert isinstance(collector, SearchBackedCollector)


def test_provider_factory_builds_firecrawl_stack_without_network_call() -> None:
    settings = RadarSettings(search_provider="firecrawl", page_provider="firecrawl")
    collector = build_web_collector(settings)

    assert isinstance(collector, SearchBackedCollector)


def test_configured_external_stack_fails_closed_during_collection() -> None:
    settings = RadarSettings(search_provider="serpapi", page_provider="firecrawl")
    collector = build_web_collector(settings)

    sources, errors = collector.collect_with_errors(_search_plan())

    assert sources == []
    assert len(errors) == 1
    assert errors[0].step == "scraper.search"
    assert errors[0].provider == "serpapi"
    assert errors[0].error_type == ExternalProviderDisabledError.__name__
    assert "explicit authorization" in errors[0].message


def test_firecrawl_stack_fails_closed_without_authorization() -> None:
    settings = RadarSettings(search_provider="firecrawl", page_provider="firecrawl")
    collector = build_web_collector(settings)

    sources, errors = collector.collect_with_errors(_search_plan())

    assert sources == []
    assert len(errors) == 1
    assert errors[0].step == "scraper.search"
    assert errors[0].provider == "firecrawl"
    assert errors[0].error_type == ExternalProviderDisabledError.__name__


def test_provider_factory_rejects_mixed_provider_configuration() -> None:
    settings = RadarSettings(search_provider="serpapi", page_provider="fixture")

    try:
        build_web_collector(settings)
    except ProviderSelectionError as exc:
        assert "Unsupported" in str(exc)
    else:
        raise AssertionError("Expected ProviderSelectionError")


def _search_plan() -> SearchPlan:
    return SearchPlan(
        query="startup brasileira com IA",
        keywords=["startup", "IA"],
        source_types=["official_site"],
        collection_plan=["configured providers"],
    )