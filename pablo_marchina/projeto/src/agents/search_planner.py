"""Build entity-specific, governed search plans for a startup.

Plans are built from verified entity URLs first. Global directory home pages
are not attached to every company, and search APIs are only used when explicitly
configured.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from typing import Any
from urllib.parse import quote_plus, urlparse


def _is_allowed_source(url: str) -> bool:
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    blocked = ("/login", "/signin", "/sign-in", "/paywall")
    return not any(term in parsed.path.casefold() for term in blocked)


_NEWS_HOSTS = (
    "exame.com",
    "valor.globo.com",
    "neofeed.com.br",
    "braziljournal.com",
    "startups.com.br",
    "revistapegn.globo.com",
    "mobiletime.com.br",
    "meioemensagem.com.br",
)
_DIRECTORY_HOSTS = (
    "distrito.me",
    "startse.com",
    "latitud.com",
    "cubo.network",
    "acestartups.com.br",
    "bossainvest.com",
    "bossainvest.com.br",
    "inovativa.online",
    "inovativabrasil.com.br",
    "endeavor.org.br",
    "abstartups.com.br",
    "anjosdobrasil.net",
    "darwinstartups.com",
    "liga.ventures",
    "openstartups.net",
    "wow.ac",
)


def _host(url: str) -> str:
    return urlparse(url).netloc.casefold().removeprefix("www.")


def _same_host(left: str, right: str) -> bool:
    left_host = _host(left)
    right_host = _host(right)
    return bool(left_host and right_host and left_host == right_host)


def _classify_source(
    url: str,
    *,
    website_url: str = "",
    source_type_hint: str | None = None,
) -> str:
    host = _host(url)
    path = urlparse(url).path.casefold()
    hint = (source_type_hint or "").casefold()
    if website_url and _same_host(url, website_url):
        if "careers" in path or "jobs" in path or "vagas" in path:
            return "job_post"
        if "blog" in path or "engineering" in path:
            return "blog"
        return "official_site"
    if hint in {"official_site", "official_website"}:
        return "official_site"
    if hint == "news" or any(value in host for value in _NEWS_HOSTS):
        return "news"
    if "linkedin.com" in host:
        return "founder_profile"
    if hint in {"blog", "job_post", "founder_profile", "search_api"}:
        return hint
    if hint in {
        "public_directory",
        "startup_program",
        "accelerator",
        "vc_portfolio",
        "event_page",
        "manual_seed",
        "directory",
    }:
        return "directory"
    if any(value in host for value in _DIRECTORY_HOSTS):
        return "directory"
    return "news"


def build_search_plan(
    startup_name: str,
    *,
    website_url: str = "",
    known_source_urls: Iterable[str] | None = None,
    max_sources: int | None = None,
) -> list[dict[str, Any]]:
    """Return a bounded plan composed only of entity-specific URLs."""
    from src.sourcing.adaptive_source_planner import SourceCandidate, source_decision_trace

    source_limit = max_sources
    if source_limit is None:
        source_limit = int(os.getenv("RADAR_ANALYSIS_MAX_SOURCES", "5"))
    source_limit = max(1, min(int(source_limit), 12))

    plan: list[dict[str, Any]] = []
    seen: set[str] = set()
    source_type_counts: dict[str, int] = {}

    def add(url: str, reason: str, *, source_type_hint: str | None = None) -> None:
        normalized_url = str(url or "").strip()
        if not normalized_url or normalized_url in seen or not _is_allowed_source(normalized_url):
            return
        seen.add(normalized_url)
        source_type = _classify_source(
            normalized_url,
            website_url=website_url,
            source_type_hint=source_type_hint,
        )
        prior_count = source_type_counts.get(source_type, 0)
        authority = {
            "official_site": 0.98,
            "news": 0.82,
            "founder_profile": 0.70,
            "job_post": 0.68,
            "blog": 0.66,
            "directory": 0.54,
            "search_api": 0.50,
        }.get(source_type, 0.50)
        candidate = SourceCandidate(
            source_name=reason,
            source_url=normalized_url,
            authority=authority,
            freshness=0.78 if source_type in {"news", "job_post", "blog", "search_api"} else 0.62,
            independence=(
                0.85
                if source_type in {"news", "directory"}
                else 0.35
                if source_type == "official_site"
                else 0.55
            ),
            known_gap_coverage=min(1.0, prior_count / 2.0),
            expected_category_coverage=1.0 / float(prior_count + 1),
            marginal_new_evidence=1.0 / float(prior_count + 1),
            estimated_cost=0.0,
            latency_ms=650.0 if source_type == "official_site" else 900.0,
            compliance_risk=0.25 if "linkedin.com" in normalized_url.casefold() else 0.10,
        )
        trace = source_decision_trace(candidate)
        plan.append(
            {
                "url": normalized_url,
                "source_type": source_type,
                "is_official_source": source_type == "official_site",
                "reason": reason,
                "expected_information_gain": trace["expected_information_gain"],
                "marginal_utility": trace["marginal_utility"],
                "estimated_cost": trace["estimated_cost"],
                "latency_ms": trace["latency_ms"],
                "compliance_risk": trace["compliance_risk"],
                "decision_formula": trace["formula"],
            }
        )
        source_type_counts[source_type] = prior_count + 1

    if website_url:
        add(website_url, f"{startup_name} official website", source_type_hint="official_site")

    for url in known_source_urls or ():
        add(str(url), "Persisted entity-specific evidence URL")

    if os.getenv("SERPAPI_API_KEY") and startup_name:
        add(
            "https://serpapi.com/search.json?q=" + quote_plus(startup_name + " startup AI Brasil"),
            "Configured search API for exact company name",
            source_type_hint="search_api",
        )

    plan.sort(
        key=lambda item: (
            1 if item["is_official_source"] else 0,
            float(item["marginal_utility"]),
        ),
        reverse=True,
    )
    return plan[:source_limit]
