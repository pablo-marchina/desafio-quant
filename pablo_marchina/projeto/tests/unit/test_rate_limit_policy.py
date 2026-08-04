from __future__ import annotations

import inspect
import os
from collections.abc import Iterator

import pytest

import src.scraping.rate_limit_policy as rate_limit_policy_module
from src.scraping.rate_limit_policy import (
    RateLimitPolicy,
    check_capability_ready,
    get_available_capabilities,
    get_rate_limit_policy,
    list_policies_requiring_api_key,
    load_rate_limit_policies,
    reset_policy_cache,
    summarize_rate_limit_policies,
)

# ── Model ──────────────────────────────────────────────────────────────────


class TestRateLimitPolicy:
    def test_minimal_fields(self) -> None:
        policy = RateLimitPolicy(
            policy_id="test-policy",
            requests_per_second=1.0,
            concurrent_requests=1,
        )
        assert policy.policy_id == "test-policy"
        assert policy.requests_per_second == 1.0
        assert policy.concurrent_requests == 1
        assert policy.max_retries == 3
        assert policy.backoff_strategy == "exponential"
        assert policy.requires_api_key is False
        assert policy.api_key_env_var is None

    def test_with_api_key_fields(self) -> None:
        policy = RateLimitPolicy(
            policy_id="api-policy",
            requests_per_second=10.0,
            concurrent_requests=2,
            requires_api_key=True,
            api_key_env_var="MY_TOKEN",
        )
        assert policy.requires_api_key is True
        assert policy.api_key_env_var == "MY_TOKEN"


# ── Registry ───────────────────────────────────────────────────────────────


class TestLoadRateLimitPolicies:
    def test_returns_all_policies(self) -> None:
        policies = load_rate_limit_policies()
        assert len(policies) == 6

    def test_includes_all_expected_policies(self) -> None:
        policies = load_rate_limit_policies()
        expected = {
            "default_polite",
            "github_api",
            "news_site",
            "directory_listing",
            "search_engine",
            "nvidia_eco",
        }
        assert expected == set(policies.keys())

    def test_github_api_requires_key(self) -> None:
        policy = get_rate_limit_policy("github_api")
        assert policy is not None
        assert policy.requires_api_key is True
        assert policy.api_key_env_var == "GITHUB_TOKEN"

    def test_default_polite_no_key(self) -> None:
        policy = get_rate_limit_policy("default_polite")
        assert policy is not None
        assert policy.requires_api_key is False
        assert policy.api_key_env_var is None

    def test_unknown_policy_returns_none(self) -> None:
        assert get_rate_limit_policy("nonexistent") is None


class TestListPoliciesRequiringApiKey:
    def test_returns_github_api_only(self) -> None:
        result = list_policies_requiring_api_key()
        ids = [p.policy_id for p in result]
        assert ids == ["github_api"]


# ── Capability readiness ───────────────────────────────────────────────────


class TestCapabilityReadiness:
    def test_no_token_no_capability(self) -> None:
        reset_policy_cache()
        caps = get_available_capabilities()
        assert isinstance(caps, set)

    def test_check_capability_ready_false_when_not_set(self) -> None:
        # Ensure env var is not set for this test
        old = os.environ.pop("GITHUB_TOKEN", None)
        try:
            reset_policy_cache()
            assert check_capability_ready("github_token") is False
        finally:
            if old is not None:
                os.environ["GITHUB_TOKEN"] = old

    def test_check_capability_ready_true_when_set(self) -> None:
        old = os.environ.get("GITHUB_TOKEN")
        os.environ["GITHUB_TOKEN"] = "test-token-123"
        try:
            reset_policy_cache()
            assert check_capability_ready("github_token") is True
        finally:
            if old is not None:
                os.environ["GITHUB_TOKEN"] = old
            else:
                del os.environ["GITHUB_TOKEN"]

    def test_check_capability_case_insensitive(self) -> None:
        old = os.environ.get("GITHUB_TOKEN")
        os.environ["GITHUB_TOKEN"] = "test-token-456"
        try:
            reset_policy_cache()
            assert check_capability_ready("GITHUB_TOKEN") is True
            assert check_capability_ready("GitHub_Token") is True
        finally:
            if old is not None:
                os.environ["GITHUB_TOKEN"] = old
            else:
                del os.environ["GITHUB_TOKEN"]

    def test_capability_unknown_policy(self) -> None:
        assert check_capability_ready("nonexistent_service_key") is False

    def test_empty_token_is_not_ready(self) -> None:
        old = os.environ.get("GITHUB_TOKEN")
        os.environ["GITHUB_TOKEN"] = "   "
        try:
            reset_policy_cache()
            assert check_capability_ready("github_token") is False
        finally:
            if old is not None:
                os.environ["GITHUB_TOKEN"] = old
            else:
                del os.environ["GITHUB_TOKEN"]


# ── Summary ────────────────────────────────────────────────────────────────


class TestSummarize:
    def test_summarize_returns_all_keys(self) -> None:
        summary = summarize_rate_limit_policies()
        expected = {
            "total_policies",
            "policy_ids",
            "policies_requiring_api_key",
            "available_capabilities",
        }
        assert expected.issubset(summary.keys())

    def test_summarize_count(self) -> None:
        summary = summarize_rate_limit_policies()
        assert summary["total_policies"] == 6
        assert "github_api" in summary["policies_requiring_api_key"]


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
            load_rate_limit_policies()
            assert len(calls) == 0, f"socket.connect called: {calls}"
        finally:
            socket.socket.connect = original  # type: ignore[assignment]

    def test_does_not_import_httpx(self) -> None:
        source = inspect.getsource(rate_limit_policy_module).lower()
        assert "httpx" not in source

    def test_does_not_import_qdrant(self) -> None:
        source = inspect.getsource(rate_limit_policy_module).lower()
        assert "qdrant" not in source


# ── Cleanup ────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_cache() -> Iterator[None]:
    reset_policy_cache()
    yield
