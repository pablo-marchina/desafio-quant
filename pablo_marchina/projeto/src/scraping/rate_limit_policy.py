from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel


class RateLimitPolicy(BaseModel):
    policy_id: str
    requests_per_second: float
    concurrent_requests: int
    max_retries: int = 3
    backoff_strategy: str = "exponential"
    description: str = ""
    requires_api_key: bool = False
    api_key_env_var: str | None = None


def _build_policy_registry() -> dict[str, RateLimitPolicy]:
    policies: dict[str, RateLimitPolicy] = {}

    policies["default_polite"] = RateLimitPolicy(
        policy_id="default_polite",
        requests_per_second=2.0,
        concurrent_requests=1,
        max_retries=3,
        backoff_strategy="exponential",
        description="Default polite rate limit for general web scraping. 2 req/s, 1 concurrent.",
    )
    policies["github_api"] = RateLimitPolicy(
        policy_id="github_api",
        requests_per_second=1.3,
        concurrent_requests=1,
        max_retries=3,
        backoff_strategy="exponential",
        description="GitHub REST API. Unauthenticated: 60 req/hr. Authenticated: 5000 req/hr.",
        requires_api_key=True,
        api_key_env_var="GITHUB_TOKEN",
    )
    policies["news_site"] = RateLimitPolicy(
        policy_id="news_site",
        requests_per_second=1.0,
        concurrent_requests=1,
        max_retries=2,
        backoff_strategy="linear",
        description="Conservative rate limit for news sites. 1 req/s, max 2 retries.",
    )
    policies["directory_listing"] = RateLimitPolicy(
        policy_id="directory_listing",
        requests_per_second=5.0,
        concurrent_requests=1,
        max_retries=2,
        backoff_strategy="exponential",
        description="Directory listing pages. 5 req/s, moderate retry.",
    )
    policies["search_engine"] = RateLimitPolicy(
        policy_id="search_engine",
        requests_per_second=1.0,
        concurrent_requests=1,
        max_retries=1,
        backoff_strategy="fixed",
        description="Search engine queries. Very conservative: 1 req/s, no retry.",
    )
    policies["nvidia_eco"] = RateLimitPolicy(
        policy_id="nvidia_eco",
        requests_per_second=3.0,
        concurrent_requests=1,
        max_retries=2,
        backoff_strategy="exponential",
        description="NVIDIA ecosystem pages. 3 req/s, moderate retry.",
    )

    return policies


_POLICY_CACHE: dict[str, RateLimitPolicy] | None = None


def load_rate_limit_policies() -> dict[str, RateLimitPolicy]:
    global _POLICY_CACHE
    if _POLICY_CACHE is None:
        _POLICY_CACHE = _build_policy_registry()
    return _POLICY_CACHE


def reset_policy_cache() -> None:
    global _POLICY_CACHE
    _POLICY_CACHE = None


def get_rate_limit_policy(policy_id: str) -> RateLimitPolicy | None:
    return load_rate_limit_policies().get(policy_id)


def get_available_capabilities() -> set[str]:
    capabilities: set[str] = set()
    for policy in load_rate_limit_policies().values():
        if policy.requires_api_key and policy.api_key_env_var:
            value = os.environ.get(policy.api_key_env_var, "")
            if value.strip():
                capabilities.add(policy.api_key_env_var.lower())
    return capabilities


def check_capability_ready(required_capability: str) -> bool:
    """Check if a required capability (e.g. ``github_token``) is available.

    .. deprecated::
        Use ``required_capability.lower() in get_available_capabilities()`` directly.
        Kept for backward compatibility.
    """
    return required_capability.lower() in get_available_capabilities()


def list_policies_requiring_api_key() -> list[RateLimitPolicy]:
    """List all policies that require an API key.

    .. deprecated::
        Use ``load_rate_limit_policies()`` and filter client-side.
        Kept for backward compatibility.
    """
    return [p for p in load_rate_limit_policies().values() if p.requires_api_key]


def summarize_rate_limit_policies() -> dict[str, Any]:
    """Produce a summary of all rate limit policies.

    .. deprecated::
        Kept for backward compatibility. Used in test assertions.
    """
    policies = load_rate_limit_policies()
    return {
        "total_policies": len(policies),
        "policy_ids": sorted(policies.keys()),
        "policies_requiring_api_key": [p.policy_id for p in policies.values() if p.requires_api_key],
        "available_capabilities": sorted(get_available_capabilities()),
    }
