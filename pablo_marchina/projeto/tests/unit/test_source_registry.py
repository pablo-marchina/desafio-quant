from __future__ import annotations

import inspect
import os
from collections.abc import Iterator
from typing import Any

import pytest

import src.scraping.source_registry as source_registry_module
from src.scraping.rate_limit_policy import load_rate_limit_policies, reset_policy_cache
from src.scraping.source_registry import (
    SourceRecord,
    list_production_enabled_sources,
    list_sources,
    list_sources_by_category,
    load_source_registry,
    reset_source_registry_cache,
    summarize_production_blockers,
    summarize_source_coverage,
    validate_source_for_production,
)

# ── Helpers ────────────────────────────────────────────────────────────────


def _make_minimal_source(**kwargs: Any) -> SourceRecord:
    defaults: dict[str, Any] = {
        "source_id": "test-source",
        "source_name": "Test Source",
        "source_category": "official_website",
        "base_url": "https://example.com",
    }
    defaults.update(kwargs)
    return SourceRecord(**defaults)


# ── SourceRecord field requirements ────────────────────────────────────────


class TestSourceRecord:
    def test_requires_minimal_fields(self) -> None:
        rec = SourceRecord(
            source_id="s-001",
            source_name="Test",
            source_category="official_website",
            base_url="https://example.com",
        )
        assert rec.source_id == "s-001"
        assert rec.production_enabled is False
        assert rec.production_blockers == []

    def test_rejects_invalid_category(self) -> None:
        with pytest.raises(ValueError, match="Invalid category"):
            SourceRecord(
                source_id="s-002",
                source_name="Bad",
                source_category="invalid_category",
                base_url="https://example.com",
            )

    def test_rejects_invalid_paywall_risk(self) -> None:
        with pytest.raises(ValueError, match="Invalid paywall_risk"):
            SourceRecord(
                source_id="s-003",
                source_name="Bad",
                source_category="media",
                base_url="https://example.com",
                paywall_risk="extreme",
            )

    def test_accepts_all_valid_categories(self) -> None:
        for cat in [
            "official_website",
            "technical_docs",
            "funding_news",
            "jobs",
            "github_or_code",
            "ecosystem_directory",
            "media",
            "nvidia_or_partner_ecosystem",
        ]:
            rec = SourceRecord(
                source_id=f"s-{cat}",
                source_name=cat,
                source_category=cat,
                base_url="https://example.com",
            )
            assert rec.source_category == cat


# ── Production blocking policies ──────────────────────────────────────────


class TestProductionBlocking:
    def test_source_with_uncalibrated_priority_is_blocked(self) -> None:
        rec = _make_minimal_source(source_id="uncalibrated-test")
        result = validate_source_for_production(rec)
        assert result["passed"] is False
        assert "source_priority_uncalibrated" in result["blockers"]

    def test_source_with_login_required_is_blocked(self) -> None:
        rec = _make_minimal_source(
            source_id="login-test",
            requires_login=True,
        )
        result = validate_source_for_production(rec)
        assert result["passed"] is False
        assert "source_requires_login" in result["blockers"]

    def test_source_with_mandatory_paywall_is_blocked(self) -> None:
        rec = _make_minimal_source(
            source_id="paywall-test",
            paywall_risk="mandatory",
        )
        result = validate_source_for_production(rec)
        assert result["passed"] is False
        assert "source_paywall_mandatory" in result["blockers"]

    def test_source_without_robots_required_is_blocked(self) -> None:
        rec = _make_minimal_source(
            source_id="norobots-test",
            robots_required=False,
        )
        result = validate_source_for_production(rec)
        assert result["passed"] is False
        assert "source_robots_not_defined" in result["blockers"]

    def test_source_with_api_key_required_and_no_capability_is_blocked(self) -> None:
        rec = _make_minimal_source(
            source_id="apikey-test",
            requires_api_key=True,
        )
        result = validate_source_for_production(rec, available_capabilities=set())
        assert result["passed"] is False
        assert "source_requires_api_key" in result["blockers"]

    def test_source_with_api_key_required_and_capability_available_passes(self) -> None:
        rec = _make_minimal_source(
            source_id="apikey-capable",
            requires_api_key=True,
            required_capability="my_api_key",
            calibrated_priority_score=1.0,
            priority_calibration_decision_id="scraping.source_priority",
        )
        result = validate_source_for_production(rec, available_capabilities={"my_api_key"})
        assert result["passed"] is True, f"blockers: {result['blockers']}"
        assert "source_requires_api_key" not in result["blockers"]

    def test_source_with_invalid_rate_limit_policy_is_blocked(self) -> None:
        rec = _make_minimal_source(
            source_id="badpolicy-test",
            rate_limit_policy_id="nonexistent_policy",
        )
        result = validate_source_for_production(rec)
        assert result["passed"] is False
        assert "rate_limit_policy_not_found" in result["blockers"]


class TestProductionEnabled:
    def test_valid_calibrated_source_passes_when_decision_exists(self) -> None:
        registry = load_source_registry()
        official = registry.get("startup_official_website")
        assert official is not None
        assert official.source_category == "official_website"
        assert official.requires_api_key is False
        assert official.requires_login is False

        result = validate_source_for_production(official)
        assert result["passed"] is True, f"blockers: {result['blockers']}"
        assert len(result["blockers"]) == 0
        assert result["production_enabled"] is True


# ── Registry query functions ──────────────────────────────────────────────


class TestListSources:
    def test_returns_all_sources(self) -> None:
        sources = list_sources()
        assert len(sources) >= 15

    def test_all_have_unique_ids(self) -> None:
        sources = list_sources()
        ids = [s.source_id for s in sources]
        assert len(ids) == len(set(ids))


class TestListSourcesByCategory:
    def test_returns_sources_for_category(self) -> None:
        official = list_sources_by_category("official_website")
        assert len(official) >= 1
        assert all(s.source_category == "official_website" for s in official)

    def test_returns_empty_for_unknown_category(self) -> None:
        result = list_sources_by_category("nonexistent")
        assert result == []


class TestListProductionEnabledSources:
    def test_returns_only_enabled_sources(self) -> None:
        enabled = list_production_enabled_sources()
        for s in enabled:
            assert s.production_enabled is True

    def test_some_sources_are_enabled(self) -> None:
        enabled = list_production_enabled_sources()
        assert len(enabled) >= 1


# ── Summaries ─────────────────────────────────────────────────────────────


class TestSummarizeSourceCoverage:
    def test_returns_all_expected_keys(self) -> None:
        summary = summarize_source_coverage()
        expected_keys = {
            "total_sources",
            "total_categories",
            "production_enabled_count",
            "blocked_count",
            "sources_by_category",
            "enabled_by_category",
        }
        assert expected_keys.issubset(summary.keys())

    def test_counts_are_coherent(self) -> None:
        summary = summarize_source_coverage()
        assert summary["total_sources"] >= 15
        assert summary["total_categories"] == 8
        assert summary["production_enabled_count"] + summary["blocked_count"] == summary["total_sources"]
        assert summary["production_enabled_count"] >= 1
        assert summary["blocked_count"] >= 1

    def test_breakdown_by_category(self) -> None:
        summary = summarize_source_coverage()
        cats = summary["sources_by_category"]
        assert "official_website" in cats
        assert "funding_news" in cats
        assert "media" in cats


class TestSummarizeProductionBlockers:
    def test_aggregates_blocker_counts(self) -> None:
        blockers = summarize_production_blockers()
        assert isinstance(blockers, dict)
        assert len(blockers) >= 1

    def test_known_blockers_present(self) -> None:
        blockers = summarize_production_blockers()
        known = {
            "source_priority_uncalibrated",
            "source_requires_login",
            "source_requires_api_key",
            "source_robots_not_defined",
            "rate_limit_policy_not_found",
        }
        assert known.issuperset(blockers.keys())

    def test_source_requires_api_key_in_blockers(self) -> None:
        blockers = summarize_production_blockers()
        if os.environ.get("GITHUB_TOKEN", "").strip():
            assert "source_requires_api_key" not in blockers
        else:
            assert "source_requires_api_key" in blockers
            assert blockers["source_requires_api_key"] >= 1


# ── Capability-aware blocking ─────────────────────────────────────────────


class TestCapabilityAwareBlocking:
    def test_github_api_search_blocked_when_no_token(self) -> None:
        registry = load_source_registry(available_capabilities=set())
        github = registry.get("github_api_search")
        assert github is not None
        assert github.production_enabled is False
        assert "source_requires_api_key" in github.production_blockers

    def test_github_api_search_unblocked_when_token_available(self) -> None:
        reset_source_registry_cache()
        registry = load_source_registry(available_capabilities={"github_token"})
        github = registry.get("github_api_search")
        assert github is not None
        assert github.production_enabled is True
        assert "source_requires_api_key" not in github.production_blockers

    def test_validate_source_for_production_with_capability(self) -> None:
        rec = _make_minimal_source(
            source_id="capable-api",
            requires_api_key=True,
            required_capability="my_service_key",
            calibrated_priority_score=1.0,
            priority_calibration_decision_id="scraping.source_priority",
        )
        result = validate_source_for_production(rec, available_capabilities={"my_service_key"})
        assert result["passed"] is True, f"blockers: {result['blockers']}"
        assert result["production_enabled"] is True

    def test_validate_source_for_production_without_capability(self) -> None:
        rec = _make_minimal_source(
            source_id="uncapable-api",
            requires_api_key=True,
            required_capability="my_service_key",
        )
        result = validate_source_for_production(rec, available_capabilities=set())
        assert result["passed"] is False
        assert "source_requires_api_key" in result["blockers"]


# ── Safety: no internet, no LLM, no Qdrant ────────────────────────────────


class TestSafety:
    def test_registry_does_not_call_internet(self) -> None:
        import socket

        original = socket.socket.connect
        calls: list[str] = []

        def tracking_connect(self: socket.socket, addr: tuple[str, int]) -> None:  # type: ignore[override]
            calls.append(str(addr))
            return original(self, addr)

        socket.socket.connect = tracking_connect  # type: ignore[assignment]
        try:
            load_source_registry()
            assert len(calls) == 0, f"socket.connect called: {calls}"
        finally:
            socket.socket.connect = original  # type: ignore[assignment]

    def test_registry_does_not_use_httpx(self) -> None:
        source = inspect.getsource(source_registry_module).lower()
        assert "httpx" not in source

    def test_registry_does_not_use_qdrant(self) -> None:
        source = inspect.getsource(source_registry_module).lower()
        assert "qdrant" not in source

    def test_registry_does_not_import_llm(self) -> None:
        source = inspect.getsource(source_registry_module).lower()
        assert "openai" not in source
        assert "anthropic" not in source
        assert "instructor" not in source


# ── All sources use valid rate limit policies ─────────────────────────────


class TestRateLimitPolicyReferences:
    def test_all_sources_use_known_policies(self) -> None:
        policies = load_rate_limit_policies()
        for src in list_sources():
            assert (
                src.rate_limit_policy_id in policies
            ), f"{src.source_id} uses unknown policy '{src.rate_limit_policy_id}'"


# ── Cleanup for tests that modify cache ────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_caches() -> Iterator[None]:
    reset_source_registry_cache()
    reset_policy_cache()
    yield
    reset_source_registry_cache()
    reset_policy_cache()
