"""Integration tests for HttpSourceCollector — governed flow with Source Registry."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import urlparse

import pytest

from src.scraping.http_collector import (
    CollectionResult,
    HttpSourceCollector,
    list_governed_sources,
)
from src.scraping.rate_limit_policy import reset_policy_cache
from src.scraping.source_registry import (
    SourceRecord,
    list_production_enabled_sources,
    reset_source_registry_cache,
)

# ── Integration test server ──────────────────────────────────────────────


class _IntegrationHandler(BaseHTTPRequestHandler):
    """Serves multiple endpoints for governed collection test."""

    def do_GET(self) -> None:
        path = urlparse(self.path).path

        routes: dict[str, tuple[int, str, str]] = {
            "/": (200, "text/html", "<html><body>Home page</body></html>"),
            "/about": (200, "text/html", "<html><body>About startup</body></html>"),
            "/team": (200, "text/html", "<html><body><h1>Team</h1><p>CTO: John</p></body></html>"),
            "/blog": (200, "text/html", "<html><body>Blog post about AI</body></html>"),
            "/robots.txt": (
                200,
                "text/plain",
                "User-agent: *\nAllow: /\nDisallow: /admin\nCrawl-delay: 0.1\n",
            ),
            "/admin": (200, "text/html", "<html><body>Admin panel</body></html>"),
            "/api/data": (200, "application/json", '{"data": "test"}'),
            "/slow": (200, "text/html", "<html><body>Slow page</body></html>"),
        }

        if path in routes:
            status, content_type, body = routes[path]
            encoded = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
        else:
            body = b"Not Found"
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:
        pass


@pytest.fixture(scope="module")
def integration_server() -> Iterator[str]:
    server = HTTPServer(("127.0.0.1", 0), _IntegrationHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"
    try:
        yield base_url
    finally:
        server.shutdown()


# ── Calibrated limits for integration tests ──────────────────────────────

_INTEGRATION_LIMITS = {
    "timeout_seconds": 10,
    "max_retries": 2,
    "backoff_base_seconds": 0.1,
}


# ── Tests ────────────────────────────────────────────────────────────────


class TestGovernedCollectionFlow:
    def test_governed_collection_uses_only_production_enabled(self, integration_server: str) -> None:
        sources = list_governed_sources()
        assert all(s.production_enabled for s in sources)

    def test_full_collection_with_source_registry(self, integration_server: str) -> None:
        list_production_enabled_sources()
        # Filter to sources with a base_url we can test against
        test_source = SourceRecord(
            source_id="integration_official",
            source_name="Integration Test Official",
            source_category="official_website",
            base_url=integration_server,
            allowed_paths=["/", "/about", "/team"],
            robots_required=True,
            rate_limit_policy_id="default_polite",
            calibrated_priority_score=1.0,
            priority_calibration_decision_id="scraping.source_priority",
            expected_evidence_types=["product_description"],
            expected_claim_types=["product_capability"],
            source_quality_prior=0.8,
            production_enabled=True,
        )

        collector = HttpSourceCollector()
        type(
            "Request",
            (object,),
            {
                "run_id": "int-test-001",
                "source_records": [test_source],
                "calibrated_limits": _INTEGRATION_LIMITS,
                "user_agent": None,
                "dry_run": False,
                "model_config": {"arbitrary_types_allowed": True},
            },
        )()
        # Convert to proper CollectionRequest
        from src.scraping.http_collector import CollectionRequest as CR

        req = CR(
            run_id="int-test-001",
            source_records=[test_source],
            calibrated_limits=_INTEGRATION_LIMITS,
        )
        result = collector.collect(req)

        assert isinstance(result, CollectionResult)
        assert result.run_id == "int-test-001"
        assert len(result.sources) >= 1

        fetched = [s for s in result.sources if s.status == "fetched"]
        assert len(fetched) >= 1, f"No sources fetched: {[s.status for s in result.sources]}"

        sfr = fetched[0]
        assert sfr.http_status_code == 200
        assert sfr.content_hash is not None
        assert sfr.latency_ms >= 0
        assert sfr.content_bytes > 0
        assert sfr.compliance_status == "compliant"

    def test_metrics_are_computed(self, integration_server: str) -> None:
        test_source = SourceRecord(
            source_id="integration_metrics",
            source_name="Integration Metrics",
            source_category="official_website",
            base_url=integration_server,
            robots_required=True,
            rate_limit_policy_id="default_polite",
            calibrated_priority_score=1.0,
            priority_calibration_decision_id="scraping.source_priority",
            production_enabled=True,
        )

        collector = HttpSourceCollector()
        from src.scraping.http_collector import CollectionRequest as CR

        req = CR(
            run_id="int-test-metrics",
            source_records=[test_source],
            calibrated_limits=_INTEGRATION_LIMITS,
        )
        result = collector.collect(req)

        metrics = result.metrics
        assert metrics.attempted_sources_count >= 1
        assert metrics.fetched_sources_count >= 1
        assert metrics.total_content_bytes > 0
        assert metrics.total_latency_ms >= 0
        assert metrics.fetch_success_rate > 0.0

    def test_robots_txt_respected(self, integration_server: str) -> None:
        # /admin is disallowed by robots.txt
        admin_source = SourceRecord(
            source_id="integration_admin",
            source_name="Admin Area",
            source_category="technical_docs",
            base_url=f"{integration_server}/admin",
            robots_required=True,
            rate_limit_policy_id="default_polite",
            calibrated_priority_score=1.0,
            priority_calibration_decision_id="scraping.source_priority",
            production_enabled=True,
        )

        collector = HttpSourceCollector()
        from src.scraping.http_collector import CollectionRequest as CR

        req = CR(
            run_id="int-test-robots",
            source_records=[admin_source],
            calibrated_limits=_INTEGRATION_LIMITS,
        )
        result = collector.collect(req)

        assert len(result.sources) == 1
        assert result.sources[0].status == "blocked"
        assert result.sources[0].error_code == "robots_disallowed"

    def test_compliance_blocked_source(self, integration_server: str) -> None:
        login_source = SourceRecord(
            source_id="integration_login",
            source_name="Login Required",
            source_category="official_website",
            base_url=integration_server,
            requires_login=True,
            robots_required=True,
            rate_limit_policy_id="default_polite",
            calibrated_priority_score=1.0,
            priority_calibration_decision_id="scraping.source_priority",
            production_enabled=True,
        )

        collector = HttpSourceCollector()
        from src.scraping.http_collector import CollectionRequest as CR

        req = CR(
            run_id="int-test-compliance",
            source_records=[login_source],
            calibrated_limits=_INTEGRATION_LIMITS,
        )
        result = collector.collect(req)

        assert len(result.sources) == 1
        assert result.sources[0].status == "blocked"
        assert result.sources[0].error_code == "compliance_blocked"

    def test_http_error_sanitized(self, integration_server: str) -> None:
        not_found_source = SourceRecord(
            source_id="integration_404",
            source_name="Not Found",
            source_category="technical_docs",
            base_url=f"{integration_server}/nonexistent-path-xyz",
            robots_required=True,
            rate_limit_policy_id="default_polite",
            calibrated_priority_score=1.0,
            priority_calibration_decision_id="scraping.source_priority",
            production_enabled=True,
        )

        collector = HttpSourceCollector()
        from src.scraping.http_collector import CollectionRequest as CR

        req = CR(
            run_id="int-test-404",
            source_records=[not_found_source],
            calibrated_limits=_INTEGRATION_LIMITS,
        )
        result = collector.collect(req)

        assert len(result.sources) == 1
        sfr = result.sources[0]
        assert sfr.status == "failed"
        assert sfr.error_message_sanitized is not None
        # The error should indicate an HTTP client error or 404
        assert any(kw in (sfr.error_message_sanitized or "") for kw in ["404", "HTTP 404", "Not Found"])

    def test_governed_source_list_is_consistent(self) -> None:
        reset_source_registry_cache()
        reset_policy_cache()
        governed = list_governed_sources()
        direct = list_production_enabled_sources()
        assert len(governed) == len(direct)
        for s in governed:
            assert s in direct


# ── Test that no LLM/Qdrant/Playwright is called ─────────────────────────


class TestSafety:
    def test_no_llm_qdrant_playwright_imported(self) -> None:
        import src.scraping.http_collector as mod

        source = str(mod.__file__)
        with open(source, encoding="utf-8") as f:
            content = f.read()

        assert "openai" not in content, "openai import in http_collector"
        assert "qdrant" not in content, "qdrant import in http_collector"
        assert "import playwright" not in content, "playwright import in http_collector"
        assert "from playwright" not in content, "playwright import in http_collector"
        assert "langchain" not in content, "langchain import in http_collector"
