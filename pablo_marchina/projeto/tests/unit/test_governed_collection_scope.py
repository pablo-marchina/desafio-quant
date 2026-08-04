from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from src.agents.scraper_agent import collect_governed_sources
from src.orchestration.node_impl import node_collect_sources
from src.orchestration.state import ProductWorkflowState


def _planned_source() -> dict[str, object]:
    return {
        "url": "https://example.ai/",
        "source_type": "official_site",
        "reason": "Verified official website",
        "expected_information_gain": 0.95,
        "marginal_utility": 0.9,
    }


def test_adaptive_plan_does_not_append_unrelated_global_registry_sources() -> None:
    captured: dict[str, object] = {}

    class FakeCollector:
        def collect(self, request):  # noqa: ANN001, ANN202
            captured["records"] = request.source_records
            return SimpleNamespace(sources=[])

    with (
        patch("src.scraping.http_collector.list_governed_sources", return_value=[object()]),
        patch("src.scraping.http_collector.HttpSourceCollector", FakeCollector),
    ):
        evidence, errors = collect_governed_sources(
            startup_name="Example AI",
            website_url="https://example.ai/",
            search_plan=[_planned_source()],
        )

    assert evidence == []
    assert errors == []
    records = captured["records"]
    assert len(records) == 1
    assert records[0].base_url == "https://example.ai/"
    assert records[0].source_id == "planned_source_0"


def test_string_fetched_at_is_serialized_without_attribute_error() -> None:
    fetched = SimpleNamespace(
        status="fetched",
        raw_html="<html>content</html>",
        extracted_text="real extracted content",
        source_url="https://example.ai/",
        source_id="planned_source_0",
        metadata={"source_category": "official_website", "source_name": "official"},
        fetched_at="2026-08-03T00:00:00+00:00",
        http_status_code=200,
        content_hash="abc",
        latency_ms=10.0,
        content_bytes=20,
        extraction_status="success",
        error_code=None,
        error_message_sanitized=None,
    )

    class FakeCollector:
        def collect(self, request):  # noqa: ANN001, ANN202
            return SimpleNamespace(sources=[fetched])

    with (
        patch("src.scraping.http_collector.list_governed_sources", return_value=[]),
        patch("src.scraping.http_collector.HttpSourceCollector", FakeCollector),
    ):
        evidence, errors = collect_governed_sources(
            startup_name="Example AI",
            website_url="https://example.ai/",
            search_plan=[_planned_source()],
        )

    assert errors == []
    assert evidence[0]["fetched_at"] == "2026-08-03T00:00:00+00:00"


def test_error_rate_includes_successful_real_evidence(monkeypatch) -> None:  # noqa: ANN001
    evidence = [
        {
            "source_url": f"https://source{idx}.example/article",
            "text": "real evidence",
            "source_type": "official_site" if idx == 0 else "news",
            "is_official_source": idx == 0,
        }
        for idx in range(3)
    ]
    monkeypatch.setenv("APP_MODE", "product")
    monkeypatch.setenv("SCRAPING_MIN_RAW_EVIDENCE", "3")
    monkeypatch.setenv("SCRAPING_MIN_DISTINCT_SOURCES", "3")
    monkeypatch.setenv("SCRAPING_MIN_SOURCE_CATEGORIES", "2")
    monkeypatch.setenv("SCRAPING_MIN_OFFICIAL_SOURCES", "1")
    monkeypatch.setenv("SCRAPING_MAX_ERROR_RATE", "0.25")

    with patch(
        "src.agents.scraper_agent.collect_governed_sources",
        return_value=(evidence, ["https://blocked.example: robots_disallowed"]),
    ):
        result = node_collect_sources(
            ProductWorkflowState(
                workflow_id="workflow-test",
                search_plan=[_planned_source()],
            )
        )

    metrics = result.state_updates["node_outputs"]["collection_metrics"]
    assert metrics["collection_error_rate"] == 0.25
    assert metrics["warnings"] == ["https://blocked.example: robots_disallowed"]
    assert str(getattr(result.status, "value", result.status)) == "completed"
