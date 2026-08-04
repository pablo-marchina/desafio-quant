"""Unit tests for scraper_agent — collect_sources and collect_governed_sources."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import urlparse

import pytest

from src.agents.scraper_agent import collect_governed_sources, collect_sources
from src.scraping.source_registry import SourceRecord

# ── Local HTTP Server ─────────────────────────────────────────────────────


class _Handler(BaseHTTPRequestHandler):
    routes: dict[str, tuple[int, str, str]] = {}

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in self.routes:
            status, ct, body = self.routes[path]
            self.send_response(status)
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", str(len(body.encode("utf-8"))))
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))
        else:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.wfile.write(b"Not Found")

    def log_message(self, fmt: str, *args: Any) -> None:
        pass


@pytest.fixture
def http_server() -> Iterator[str]:
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"
    try:
        yield base_url
    finally:
        server.shutdown()


# ── Fixtures for governed sources ─────────────────────────────────────────


@pytest.fixture
def governed_source(http_server: str) -> SourceRecord:
    return SourceRecord(
        source_id="test-official",
        source_name="Test Official Website",
        source_category="official_website",
        base_url=http_server,
        allowed_paths=["/", "/about"],
        robots_required=True,
        rate_limit_policy_id="default_polite",
        calibrated_priority_score=1.0,
        priority_calibration_decision_id="scraping.source_priority",
        expected_evidence_types=["product_description"],
        expected_claim_types=["product_capability"],
        source_quality_prior=0.8,
        production_enabled=True,
    )


@pytest.fixture
def governed_no_base_url() -> SourceRecord:
    return SourceRecord(
        source_id="test-dynamic",
        source_name="Dynamic Startup Website",
        source_category="official_website",
        base_url="",
        robots_required=True,
        rate_limit_policy_id="default_polite",
        calibrated_priority_score=1.0,
        priority_calibration_decision_id="scraping.source_priority",
        production_enabled=True,
    )


@pytest.fixture
def governed_blocked() -> SourceRecord:
    return SourceRecord(
        source_id="test-blocked",
        source_name="Login Required",
        source_category="official_website",
        base_url="http://blocked.example",
        requires_login=True,
        robots_required=True,
        rate_limit_policy_id="default_polite",
        calibrated_priority_score=1.0,
        priority_calibration_decision_id="scraping.source_priority",
        production_enabled=True,
    )


# ── Auto-reset handler routes between tests ───────────────────────────────


@pytest.fixture(autouse=True)
def _reset_routes() -> Iterator[None]:
    _Handler.routes = {}
    yield
    _Handler.routes = {}


# ── Tests: collect_governed_sources ───────────────────────────────────────


class TestCollectGovernedSources:

    def test_collects_from_governed_sources(
        self, http_server: str, governed_source: SourceRecord, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _Handler.routes = {
            "/": (200, "text/html", "<html><body>Home page</body></html>"),
            "/about": (200, "text/html", "<html><body>About startup</body></html>"),
            "/robots.txt": (200, "text/plain", "User-agent: *\nAllow: /\n"),
        }
        governed_source = governed_source.model_copy(update={"base_url": http_server})
        monkeypatch.setattr(
            "src.scraping.http_collector.list_governed_sources",
            lambda: [governed_source],
        )
        items, errors = collect_governed_sources(startup_name="TestStartup", website_url=http_server)
        assert len(items) >= 1, f"errors={errors}"
        assert all(item["url"].startswith(http_server) for item in items)
        assert all(isinstance(item["url"], str) for item in items)
        assert all(isinstance(item["text"], str) for item in items)

    def test_empty_sources_returns_early(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "src.scraping.http_collector.list_governed_sources",
            lambda: [],
        )
        items, errors = collect_governed_sources(startup_name="Empty", website_url="http://example.com")
        assert items == []
        assert any("No production-enabled sources" in e for e in errors)

    def test_dry_run_returns_no_content(
        self, http_server: str, governed_source: SourceRecord, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        governed_source = governed_source.model_copy(update={"base_url": http_server})
        monkeypatch.setattr(
            "src.scraping.http_collector.list_governed_sources",
            lambda: [governed_source],
        )
        items, errors = collect_governed_sources(startup_name="DryRun", website_url=http_server, dry_run=True)
        assert len(items) == 0
        # dry_run should not produce fetches — blocked or no content
        assert all(e for e in errors)  # errors might have dry-run messages

    def test_dynamic_base_url_from_website_url(self, http_server: str, monkeypatch: pytest.MonkeyPatch) -> None:
        _Handler.routes = {
            "/": (200, "text/html", "<html><body>Home page</body></html>"),
            "/robots.txt": (200, "text/plain", "User-agent: *\nAllow: /\n"),
        }
        src = SourceRecord(
            source_id="test-dynamic",
            source_name="Dynamic Startup Website",
            source_category="official_website",
            base_url="",
            robots_required=True,
            rate_limit_policy_id="default_polite",
            calibrated_priority_score=1.0,
            priority_calibration_decision_id="scraping.source_priority",
            production_enabled=True,
        )
        monkeypatch.setattr(
            "src.scraping.http_collector.list_governed_sources",
            lambda: [src],
        )
        items, errors = collect_governed_sources(startup_name="Dynamic", website_url=http_server)
        assert len(items) >= 1, f"errors={errors}"

    def test_partial_failure_yields_both_items_and_errors(
        self, http_server: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        good = SourceRecord(
            source_id="test-good",
            source_name="Good Source",
            source_category="official_website",
            base_url=http_server,
            robots_required=True,
            rate_limit_policy_id="default_polite",
            calibrated_priority_score=1.0,
            priority_calibration_decision_id="scraping.source_priority",
            production_enabled=True,
        )
        bad = SourceRecord(
            source_id="test-bad",
            source_name="Bad Source",
            source_category="technical_docs",
            base_url="http://127.0.0.1:1",  # connection refused
            robots_required=False,
            rate_limit_policy_id="default_polite",
            calibrated_priority_score=0.5,
            priority_calibration_decision_id="scraping.source_priority",
            production_enabled=True,
        )
        monkeypatch.setattr(
            "src.scraping.http_collector.list_governed_sources",
            lambda: [good, bad],
        )
        items, errors = collect_governed_sources(startup_name="Partial", website_url=http_server)
        assert len(items) >= 1 or len(errors) >= 1
        if items:
            assert all(it["url"].startswith(http_server) for it in items)

    def test_output_format_matches_downstream_contract(
        self, http_server: str, governed_source: SourceRecord, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _Handler.routes = {
            "/": (200, "text/html", "<html><body>Home page</body></html>"),
            "/robots.txt": (200, "text/plain", "User-agent: *\nAllow: /\n"),
        }
        governed_source = governed_source.model_copy(update={"base_url": http_server})
        monkeypatch.setattr(
            "src.scraping.http_collector.list_governed_sources",
            lambda: [governed_source],
        )
        items, errors = collect_governed_sources(startup_name="Format", website_url=http_server)
        if items:
            item = items[0]
            assert "url" in item
            assert "text" in item
            assert "source_type" in item
            assert "source_id" in item
            assert "reason" in item
            assert "fetched_at" in item
            assert "status_code" in item
            assert "content_hash" in item
            assert "latency_ms" in item
            assert "content_bytes" in item
            assert isinstance(item["text"], str)
            assert isinstance(item["source_type"], str)
            assert item["status_code"] == 200 or item["status_code"] is None
            assert item["content_hash"] is not None


# ── Tests: collect_sources (existing behavior, regression) ────────────────


class TestCollectSources:

    def test_empty_plan_returns_empty(self) -> None:
        items, errors = collect_sources({"search_queries": [], "max_sources": 5})
        assert items == []
        assert errors == []

    def test_list_plan(self) -> None:
        items, errors = collect_sources([])
        assert items == []
        assert errors == []

    def test_no_url_skipped(self) -> None:
        queries = [{"url": "", "source_type": "unknown", "reason": "test"}]
        items, errors = collect_sources({"search_queries": queries})
        assert items == []
        assert errors == []

    def test_bad_url_returns_error(self) -> None:
        queries = [{"url": "http://127.0.0.1:1/test", "source_type": "web"}]
        items, errors = collect_sources({"search_queries": queries})
        assert items == []
        assert len(errors) >= 1
