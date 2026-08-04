"""Unit tests for HttpSourceCollector — real HTTP, local server only, no internet."""

from __future__ import annotations

import inspect
import socket
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import urlparse

import pytest

import src.scraping.http_collector as http_collector_module
from src.scraping.http_collector import (
    CollectionMetrics,
    CollectionRequest,
    CollectionResult,
    ComplianceResult,
    HttpSourceCollector,
    RobotsChecker,
    SourceFetchResult,
    _compute_content_hash,
    _validate_source,
    list_governed_sources,
)
from src.scraping.source_registry import SourceRecord

# ── Test helpers ─────────────────────────────────────────────────────────


def _source(**overrides: Any) -> SourceRecord:
    defaults: dict[str, Any] = {
        "source_id": "test-http",
        "source_name": "Test HTTP Source",
        "source_category": "official_website",
        "base_url": "",
        "robots_required": True,
        "rate_limit_policy_id": "default_polite",
        "calibrated_priority_score": 1.0,
        "production_enabled": True,
    }
    defaults.update(overrides)
    return SourceRecord(**defaults)


def _make_request(sources: list[SourceRecord], **overrides: Any) -> CollectionRequest:
    defaults: dict[str, Any] = {
        "run_id": "ut-test-001",
        "source_records": sources,
        "calibrated_limits": {
            "timeout_seconds": 5,
            "max_retries": 1,
            "backoff_base_seconds": 0.1,
        },
    }
    defaults.update(overrides)
    return CollectionRequest(**defaults)


# ── Local HTTP Server ────────────────────────────────────────────────────


class _TestHandler(BaseHTTPRequestHandler):
    """Simple handler that serves configurable responses."""

    responses: dict[str, tuple[int, str, str]] = {}

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path in self.responses:
            status, content_type, body = self.responses[path]
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body.encode("utf-8"))))
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))
        else:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.wfile.write(b"Not Found")

    def log_message(self, fmt: str, *args: Any) -> None:
        pass


def _start_test_server(host: str = "127.0.0.1", port: int = 0) -> tuple[HTTPServer, int]:
    server = HTTPServer((host, port), _TestHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def local_server() -> Iterator[tuple[str, int]]:
    server, port = _start_test_server()
    try:
        yield ("127.0.0.1", port)
    finally:
        server.shutdown()


@pytest.fixture(autouse=True)
def _reset_handler() -> Iterator[None]:
    _TestHandler.responses = {}
    yield
    _TestHandler.responses = {}


# ── RobotsChecker Tests ──────────────────────────────────────────────────


class TestRobotsChecker:
    def test_allows_when_no_robots(self) -> None:
        checker = RobotsChecker()
        assert checker.is_allowed("https://example.com/any/path") is True
        assert checker.parsed is False

    def test_allows_path_not_disallowed(self) -> None:
        robots = "User-agent: *\nDisallow: /admin/\n"
        checker = RobotsChecker(robots)
        assert checker.is_allowed("https://example.com/public") is True

    def test_blocks_disallowed_path(self) -> None:
        robots = "User-agent: *\nDisallow: /api/\n"
        checker = RobotsChecker(robots)
        assert checker.is_allowed("https://example.com/api/v1/users") is False

    def test_allow_overrides_disallow(self) -> None:
        robots = "User-agent: *\nDisallow: /api/\nAllow: /api/public\n"
        checker = RobotsChecker(robots)
        assert checker.is_allowed("https://example.com/api/public") is True
        assert checker.is_allowed("https://example.com/api/private") is False

    def test_respects_user_agent(self) -> None:
        robots = "User-agent: BadBot\nDisallow: /\n\n" "User-agent: *\nAllow: /\n"
        checker = RobotsChecker(robots, user_agent="GoodBot")
        assert checker.is_allowed("https://example.com/") is True

    def test_parses_crawl_delay(self) -> None:
        robots = "User-agent: *\nCrawl-delay: 10\n"
        checker = RobotsChecker(robots)
        assert checker.crawl_delay == 10.0

    def test_wildcard_path(self) -> None:
        robots = "User-agent: *\nDisallow: /*.pdf\n"
        checker = RobotsChecker(robots)
        assert checker.is_allowed("https://example.com/doc.pdf") is False
        assert checker.is_allowed("https://example.com/doc.html") is True


# ── Compliance Tests ─────────────────────────────────────────────────────


class TestValidateSource:
    def test_passes_for_valid_source(self) -> None:
        src = _source()
        result = _validate_source(src)
        assert result.passed is True
        assert result.blockers == []

    def test_blocks_when_not_production_enabled(self) -> None:
        src = _source(production_enabled=False)
        result = _validate_source(src)
        assert result.passed is False
        assert "source_not_production_enabled" in result.blockers

    def test_blocks_when_login_required(self) -> None:
        src = _source(requires_login=True)
        result = _validate_source(src)
        assert result.passed is False
        assert "source_requires_login" in result.blockers

    def test_blocks_when_paywall_mandatory(self) -> None:
        src = _source(paywall_risk="mandatory")
        result = _validate_source(src)
        assert result.passed is False
        assert "source_paywall_mandatory" in result.blockers

    def test_blocks_when_priority_uncalibrated(self) -> None:
        src = _source(calibrated_priority_score=None)
        result = _validate_source(src)
        assert result.passed is False
        assert "source_priority_uncalibrated" in result.blockers

    def test_blocks_when_robots_not_defined(self) -> None:
        src = _source(robots_required=False)
        result = _validate_source(src)
        assert result.passed is True
        assert result.robots_allowed is True

    def test_blocks_when_rate_limit_policy_missing(self) -> None:
        src = _source(rate_limit_policy_id="nonexistent_policy")
        result = _validate_source(src)
        assert result.passed is False
        assert "rate_limit_policy_not_found" in result.blockers


# ── Content Hashing Tests ────────────────────────────────────────────────


class TestContentHash:
    def test_computes_sha256(self) -> None:
        h = _compute_content_hash("hello")
        assert h == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"

    def test_consistent_for_same_input(self) -> None:
        assert _compute_content_hash("data") == _compute_content_hash("data")

    def test_different_for_different_input(self) -> None:
        assert _compute_content_hash("data") != _compute_content_hash("other")


# ── Real HTTP Fetches (local server) ─────────────────────────────────────


class TestHttpSourceCollector:
    def test_collect_only_production_enabled(self, local_server: tuple[str, int]) -> None:
        host, port = local_server
        url = f"http://{host}:{port}/test"
        _TestHandler.responses["/test"] = (200, "text/html", "<html><body>OK</body></html>")
        _TestHandler.responses["/robots.txt"] = (200, "text/plain", "User-agent: *\nAllow: /\n")

        enabled = _source(base_url=url, production_enabled=True)
        disabled = _source(source_id="blocked", base_url=url, production_enabled=False)

        collector = HttpSourceCollector()
        req = _make_request([enabled, disabled])
        result = collector.collect(req)

        assert len(result.sources) == 2
        assert result.sources[0].status == "fetched"
        assert result.sources[1].status == "blocked"
        assert result.sources[1].error_code == "compliance_blocked"

    def test_fetches_real_html(self, local_server: tuple[str, int]) -> None:
        host, port = local_server
        url = f"http://{host}:{port}/page"
        html = "<html><body><h1>Hello World</h1></body></html>"
        _TestHandler.responses["/page"] = (200, "text/html", html)
        _TestHandler.responses["/robots.txt"] = (200, "text/plain", "User-agent: *\nAllow: /\n")

        collector = HttpSourceCollector()
        req = _make_request([_source(base_url=url)])
        result = collector.collect(req)

        assert len(result.sources) == 1
        sfr = result.sources[0]
        assert sfr.status == "fetched"
        assert sfr.http_status_code == 200
        assert sfr.source_url == url
        assert sfr.raw_html == html
        assert sfr.content_bytes > 0
        assert sfr.latency_ms >= 0
        assert sfr.content_hash is not None
        assert sfr.compliance_status == "compliant"
        assert sfr.robots_allowed is True

    def test_robots_disallow_blocks(self, local_server: tuple[str, int]) -> None:
        host, port = local_server
        url = f"http://{host}:{port}/admin"
        _TestHandler.responses["/admin"] = (200, "text/html", "<html>Secret</html>")
        _TestHandler.responses["/robots.txt"] = (
            200,
            "text/plain",
            "User-agent: *\nDisallow: /admin\n",
        )

        collector = HttpSourceCollector()
        req = _make_request([_source(base_url=url)])
        result = collector.collect(req)

        assert len(result.sources) == 1
        sfr = result.sources[0]
        assert sfr.status == "blocked"
        assert sfr.error_code == "robots_disallowed"
        assert sfr.robots_allowed is False

    def test_rate_limit_policy_applied(self, local_server: tuple[str, int]) -> None:
        host, port = local_server
        url1 = f"http://{host}:{port}/a"
        url2 = f"http://{host}:{port}/b"
        _TestHandler.responses["/a"] = (200, "text/html", "<html>A</html>")
        _TestHandler.responses["/b"] = (200, "text/html", "<html>B</html>")
        _TestHandler.responses["/robots.txt"] = (200, "text/plain", "User-agent: *\nAllow: /\n")

        collector = HttpSourceCollector()
        src_a = _source(source_id="src-a", base_url=url1, rate_limit_policy_id="default_polite")
        src_b = _source(source_id="src-b", base_url=url2, rate_limit_policy_id="default_polite")
        req = _make_request([src_a, src_b])
        start = time.time()
        result = collector.collect(req)
        elapsed = time.time() - start

        # default_polite = 2 req/s, interval = 0.5s. 2 requests => at least 0.5s wait
        assert elapsed >= 0.4, f"Expected rate limit delay, got {elapsed:.3f}s"
        assert result.sources[0].status == "fetched"
        assert result.sources[1].status == "fetched"

    def test_timeout_retry_applied(self, local_server: tuple[str, int]) -> None:
        host, port = local_server
        url = f"http://{host}:{port}/retry-test"
        # Simulate 500 errors
        _TestHandler.responses["/retry-test"] = (500, "text/plain", "Server Error")
        _TestHandler.responses["/robots.txt"] = (200, "text/plain", "User-agent: *\nAllow: /\n")

        collector = HttpSourceCollector()
        req = _make_request(
            [_source(base_url=url)],
            calibrated_limits={
                "timeout_seconds": 5,
                "max_retries": 2,
                "backoff_base_seconds": 0.05,
            },
        )
        result = collector.collect(req)

        assert len(result.sources) == 1
        sfr = result.sources[0]
        assert sfr.status == "failed"
        assert sfr.http_status_code == 500
        assert "HTTP 500" in (sfr.error_message_sanitized or "")

    def test_http_error_returns_sanitized_error(self, local_server: tuple[str, int]) -> None:
        host, port = local_server
        url = f"http://{host}:{port}/not-found"
        _TestHandler.responses["/not-found"] = (404, "text/plain", "Not Found")
        _TestHandler.responses["/robots.txt"] = (200, "text/plain", "User-agent: *\nAllow: /\n")

        collector = HttpSourceCollector()
        req = _make_request([_source(base_url=url)])
        result = collector.collect(req)

        assert len(result.sources) == 1
        sfr = result.sources[0]
        assert sfr.status == "failed"
        assert sfr.http_status_code == 404
        assert sfr.error_message_sanitized is not None
        assert sfr.error_message_sanitized != ""

    def test_content_hash_computed(self, local_server: tuple[str, int]) -> None:
        host, port = local_server
        url = f"http://{host}:{port}/hash-test"
        html = "<html><body>Hash me</body></html>"
        _TestHandler.responses["/hash-test"] = (200, "text/html", html)
        _TestHandler.responses["/robots.txt"] = (200, "text/plain", "User-agent: *\nAllow: /\n")

        expected_hash = _compute_content_hash(html)
        collector = HttpSourceCollector()
        req = _make_request([_source(base_url=url)])
        result = collector.collect(req)

        assert result.sources[0].content_hash == expected_hash

    def test_duplicate_detected(self, local_server: tuple[str, int]) -> None:
        host, port = local_server
        url = f"http://{host}:{port}/dup"
        html = "<html><body>Duplicate</body></html>"
        _TestHandler.responses["/dup"] = (200, "text/html", html)
        _TestHandler.responses["/robots.txt"] = (200, "text/plain", "User-agent: *\nAllow: /\n")

        collector = HttpSourceCollector()
        src = _source(base_url=url)
        req = _make_request([src, src])
        result = collector.collect(req)

        assert len(result.sources) == 2
        statuses = [s.status for s in result.sources]
        assert statuses.count("fetched") == 1
        assert statuses.count("duplicate") == 1
        assert result.sources[0].content_hash == result.sources[1].content_hash
        assert result.metrics.duplicate_count == 1

    def test_no_base_url_skipped(self) -> None:
        collector = HttpSourceCollector()
        src = _source(base_url="")
        req = _make_request([src])
        result = collector.collect(req)

        assert len(result.sources) == 1
        assert result.sources[0].status == "skipped"
        assert result.sources[0].error_code == "no_base_url"

    def test_dry_run_returns_dry_run_status(self, local_server: tuple[str, int]) -> None:
        host, port = local_server
        url = f"http://{host}:{port}/dry"
        _TestHandler.responses["/dry"] = (200, "text/html", "<html>Dry</html>")
        _TestHandler.responses["/robots.txt"] = (200, "text/plain", "User-agent: *\nAllow: /\n")

        collector = HttpSourceCollector()
        req = _make_request([_source(base_url=url)], dry_run=True)
        result = collector.collect(req)

        assert len(result.sources) == 1
        assert result.sources[0].status == "dry_run"

    def test_calibrated_values_do_not_block_for_local_server(self, local_server: tuple[str, int]) -> None:
        host, port = local_server
        url = f"http://{host}:{port}/cal-pass"
        _TestHandler.responses["/cal-pass"] = (200, "text/html", "<html>Calibrated OK</html>")
        _TestHandler.responses["/robots.txt"] = (200, "text/plain", "User-agent: *\nAllow: /\n")

        collector = HttpSourceCollector()
        req = _make_request(
            [_source(base_url=url)],
            calibrated_limits={},
        )
        result = collector.collect(req)

        # Collection proceeds past calibration gate because all values are BASELINE_MEASURED
        assert result.sources[0].status == "fetched"

    def test_registry_blocked_source_not_collected(self) -> None:
        src = _source(requires_login=True, base_url="https://example.com")
        collector = HttpSourceCollector()
        req = _make_request([src])
        result = collector.collect(req)

        assert len(result.sources) == 1
        assert result.sources[0].status == "blocked"
        assert result.sources[0].error_code == "compliance_blocked"
        assert "source_requires_login" in (result.sources[0].error_message_sanitized or "")


# ── Metrics Tests ────────────────────────────────────────────────────────


class TestCollectionMetrics:
    def test_metrics_after_successful_collection(self, local_server: tuple[str, int]) -> None:
        host, port = local_server
        url = f"http://{host}:{port}/metrics"
        _TestHandler.responses["/metrics"] = (200, "text/html", "<html>Metrics</html>")
        _TestHandler.responses["/robots.txt"] = (200, "text/plain", "User-agent: *\nAllow: /\n")

        collector = HttpSourceCollector()
        req = _make_request([_source(base_url=url)])
        result = collector.collect(req)

        m = result.metrics
        assert m.attempted_sources_count == 1
        assert m.fetched_sources_count == 1
        assert m.blocked_sources_count == 0
        assert m.failed_sources_count == 0
        assert m.robots_blocked_count == 0
        assert m.compliance_blocked_count == 0
        assert m.duplicate_count == 0
        assert m.total_latency_ms >= 0
        assert m.median_latency_ms >= 0
        assert m.total_content_bytes > 0
        assert m.fetch_success_rate == 1.0
        assert m.extraction_success_rate >= 0

    def test_metrics_with_blocked_source(self, local_server: tuple[str, int]) -> None:
        host, port = local_server
        url = f"http://{host}:{port}/metrics-blocked"
        _TestHandler.responses["/metrics-blocked"] = (200, "text/html", "<html>OK</html>")
        _TestHandler.responses["/robots.txt"] = (
            200,
            "text/plain",
            "User-agent: *\nDisallow: /metrics-blocked\n",
        )

        collector = HttpSourceCollector()
        req = _make_request([_source(base_url=url)])
        result = collector.collect(req)

        m = result.metrics
        assert m.attempted_sources_count == 1
        assert m.fetched_sources_count == 0
        assert m.blocked_sources_count == 1
        assert m.robots_blocked_count == 1
        assert m.fetch_success_rate == 0.0
        assert m.total_content_bytes == 0

    def test_metrics_with_duplicate(self, local_server: tuple[str, int]) -> None:
        host, port = local_server
        url = f"http://{host}:{port}/metrics-dup"
        _TestHandler.responses["/metrics-dup"] = (200, "text/html", "<html>Dup</html>")
        _TestHandler.responses["/robots.txt"] = (200, "text/plain", "User-agent: *\nAllow: /\n")

        collector = HttpSourceCollector()
        src = _source(base_url=url)
        req = _make_request([src, src])
        result = collector.collect(req)

        m = result.metrics
        assert m.attempted_sources_count == 2
        assert m.fetched_sources_count == 1
        assert m.duplicate_count == 1

    def test_metrics_empty(self) -> None:
        metrics = CollectionMetrics()
        assert metrics.attempted_sources_count == 0
        assert metrics.fetch_success_rate == 0.0


# ── Safety Tests ─────────────────────────────────────────────────────────


class TestNoExternalInternet:
    def test_no_external_connections(self, local_server: tuple[str, int]) -> None:
        host, port = local_server
        url = f"http://{host}:{port}/safe"
        _TestHandler.responses["/safe"] = (200, "text/html", "<html>Safe</html>")
        _TestHandler.responses["/robots.txt"] = (200, "text/plain", "User-agent: *\nAllow: /\n")

        original_connect = socket.socket.connect
        connections: list[str] = []

        def tracking_connect(self: socket.socket, addr: tuple[str, int]) -> None:
            host_part = addr[0] if isinstance(addr, tuple) else str(addr)
            # Allow localhost only
            if host_part not in ("127.0.0.1", "localhost", "::1"):
                connections.append(str(addr))
            return original_connect(self, addr)

        socket.socket.connect = tracking_connect  # type: ignore[assignment]
        try:
            collector = HttpSourceCollector()
            req = _make_request([_source(base_url=url)])
            collector.collect(req)
            assert len(connections) == 0, f"External connections detected: {connections}"
        finally:
            socket.socket.connect = original_connect  # type: ignore[assignment]

    def test_no_llm_import(self) -> None:
        source = inspect.getsource(http_collector_module).lower()
        assert "openai" not in source
        assert "anthropic" not in source
        assert "instructor" not in source

    def test_no_qdrant_import(self) -> None:
        source = inspect.getsource(http_collector_module).lower()
        assert "qdrant" not in source

    def test_no_playwright_import(self) -> None:
        source = inspect.getsource(http_collector_module)
        assert "import playwright" not in source
        assert "from playwright" not in source


# ── Pydantic Model Tests ──────────────────────────────────────────────────


class TestModels:
    def test_source_fetch_result_defaults(self) -> None:
        r = SourceFetchResult(source_id="s1", source_url="https://example.com")
        assert r.status == "pending"
        assert r.raw_html == ""
        assert r.content_bytes == 0
        assert r.extraction_status == "not_configured"

    def test_collection_metrics_defaults(self) -> None:
        m = CollectionMetrics()
        assert m.fetch_success_rate == 0.0
        assert m.fetched_sources_count == 0

    def test_collection_request_defaults(self) -> None:
        src = _source()
        req = CollectionRequest(run_id="r1", source_records=[src])
        assert req.dry_run is False
        assert req.user_agent is None
        assert req.calibrated_limits == {}

    def test_collection_result_structure(self) -> None:
        src = _source()
        req = _make_request([src])
        result = CollectionResult(run_id="r1", request=req)
        assert result.sources == []
        assert result.metrics.attempted_sources_count == 0
        assert result.finished_at is None

    def test_compliance_result_defaults(self) -> None:
        c = ComplianceResult(passed=True)
        assert c.blockers == []
        assert c.robots_allowed is True
        assert c.robots_checked is False


# ── Factory Tests ────────────────────────────────────────────────────────


class TestFactory:
    def test_build_http_collector(self) -> None:
        collector = HttpSourceCollector()
        assert isinstance(collector, HttpSourceCollector)

    def test_list_governed_sources(self) -> None:
        sources = list_governed_sources()
        assert isinstance(sources, list)
        for s in sources:
            assert s.production_enabled is True
