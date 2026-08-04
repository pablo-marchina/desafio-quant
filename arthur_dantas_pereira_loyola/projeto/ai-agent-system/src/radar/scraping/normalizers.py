from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

from radar.schemas import SourceCandidate, SourceDocument
from radar.schemas.evidence import SourceType


SOURCE_TYPE_ALIASES: dict[str, SourceType] = {
    "official": "official_site",
    "official_site": "official_site",
    "site": "official_site",
    "blog": "blog",
    "careers": "careers",
    "jobs": "careers",
    "founder": "founder_profile",
    "founder_profile": "founder_profile",
    "directory": "startup_directory",
    "startup_directory": "startup_directory",
    "news": "news",
    "nvidia": "nvidia_documentation",
    "nvidia_documentation": "nvidia_documentation",
}


def normalize_search_result_payload(
    payload: Mapping[str, Any],
    *,
    provider: str,
    rank: int | None = None,
) -> SourceCandidate:
    """Convert a raw search API result into a traceable source candidate."""

    url = _first_text(payload, ("url", "source_url", "link", "result_url"))
    if not url:
        raise ValueError("Raw search result payload must include a URL.")

    candidate_rank = _rank_from_payload(payload, fallback=rank)
    return SourceCandidate(
        url=url,
        domain=_first_text(payload, ("domain", "host")) or _domain_from_url(url),
        source_type=_normalize_source_type(_first_text(payload, ("source_type", "type", "kind"))),
        title=_first_text(payload, ("title", "name", "headline")),
        snippet=_first_text(payload, ("snippet", "description", "summary", "content_summary")),
        rank=candidate_rank,
        provider=provider,
        raw_payload=dict(payload),
    )


def normalize_search_result_payloads(
    payloads: list[Mapping[str, Any]],
    *,
    provider: str,
) -> list[SourceCandidate]:
    return [
        normalize_search_result_payload(payload, provider=provider, rank=index)
        for index, payload in enumerate(payloads, start=1)
    ]


def normalize_source_payload(
    payload: Mapping[str, Any],
    *,
    collection_method: str,
) -> SourceDocument:
    """Convert a raw collector/API payload into the pipeline SourceDocument contract."""

    url = _first_text(payload, ("url", "source_url", "link"))
    text = _first_text(payload, ("text", "content", "body", "markdown"))
    if not url:
        raise ValueError("Raw source payload must include a URL.")
    if not text:
        raise ValueError("Raw source payload must include text content.")

    domain = _first_text(payload, ("domain", "host")) or _domain_from_url(url)
    source_type = _normalize_source_type(_first_text(payload, ("source_type", "type", "kind")))

    return SourceDocument(
        url=url,
        domain=domain,
        source_type=source_type,
        title=_first_text(payload, ("title", "name", "headline")),
        text=text,
        collection_method=collection_method,
    )


def normalize_source_payloads(
    payloads: list[Mapping[str, Any]],
    *,
    collection_method: str,
) -> list[SourceDocument]:
    return [
        normalize_source_payload(payload, collection_method=collection_method)
        for payload in payloads
    ]


def normalize_collected_page_payload(
    payload: Mapping[str, Any],
    *,
    collection_method: str,
    candidate: SourceCandidate | None = None,
) -> SourceDocument:
    """Normalize a collected page, optionally enriching it with search metadata."""

    enriched_payload = dict(payload)
    if candidate is not None:
        enriched_payload.setdefault("url", str(candidate.url))
        enriched_payload.setdefault("domain", candidate.domain)
        enriched_payload.setdefault("source_type", candidate.source_type)
        enriched_payload.setdefault("title", candidate.title)
    return normalize_source_payload(enriched_payload, collection_method=collection_method)


def _first_text(payload: Mapping[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _domain_from_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.lower()


def _normalize_source_type(raw_type: str | None) -> SourceType:
    if not raw_type:
        return "other"
    return SOURCE_TYPE_ALIASES.get(raw_type.strip().lower(), "other")


def _rank_from_payload(payload: Mapping[str, Any], *, fallback: int | None) -> int | None:
    value = payload.get("rank") or payload.get("position")
    if isinstance(value, int) and value >= 1:
        return value
    if isinstance(value, str) and value.isdigit() and int(value) >= 1:
        return int(value)
    return fallback
