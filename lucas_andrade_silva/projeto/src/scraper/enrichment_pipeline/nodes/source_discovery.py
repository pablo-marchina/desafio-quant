from __future__ import annotations

from urllib.parse import urlsplit
from time import perf_counter

from .llm_summarize import append_error
from .web_scrape import DDGS, _rate_limit
from .. import config
from ..state import EnrichmentState

SOURCE_FIELDS = (
    ("website_url", "website"),
    ("website", "website"),
    ("site", "website"),
    ("source_url", "website"),
    ("linkedin_url", "linkedin"),
    ("crunchbase_url", "crunchbase"),
)


def build_discovery_query(candidate: dict[str, object]) -> str:
    company = str(candidate.get("company_name") or candidate.get("nome") or "").strip()
    segment = str(candidate.get("segment") or "").strip()
    return " ".join(part for part in (company, segment, "Brasil startup tecnologia") if part).strip()


def _candidate_source(url: str, source_type: str) -> dict[str, object]:
    return {
        "url": url,
        "source_type": source_type,
        "origin": "candidate_field",
        "title": None,
        "snippet": None,
        "raw_text": None,
        "metadata": {},
    }


def _search_candidates(candidate: dict[str, object]) -> list[dict[str, object]]:
    if DDGS is None:
        raise RuntimeError("ddgs nao esta instalado")
    query = build_discovery_query(candidate)
    if not query:
        return []
    rows: list[dict[str, object]] = []
    _rate_limit()
    with DDGS(timeout=config.HTTP_TIMEOUT_SECONDS) as ddgs:
        for result in ddgs.text(query, max_results=config.MAX_SOURCE_CANDIDATES):
            url = str(result.get("href") or result.get("url") or "").strip()
            if not url.startswith("http"):
                continue
            rows.append(
                {
                    "url": url,
                    "source_type": "web_search",
                    "origin": "ddg",
                    "title": str(result.get("title") or "") or None,
                    "snippet": str(result.get("body") or result.get("snippet") or "") or None,
                    "raw_text": None,
                    "metadata": {"host": (urlsplit(url).hostname or "").removeprefix("www.")},
                }
            )
    return rows


def source_discovery_node(state: EnrichmentState) -> dict[str, object]:
    if not state.get("run_identity_phase", True):
        return {"source_candidates": list(state.get("source_candidates", [])), "errors": state.get("errors", {})}
    started = perf_counter()
    candidate = state.get("candidate", {})
    errors = state.get("errors", {})
    rows: list[dict[str, object]] = []
    for field, source_type in SOURCE_FIELDS:
        value = str(candidate.get(field) or "").strip()
        if value.startswith("http"):
            rows.append(_candidate_source(value, source_type))
    try:
        rows.extend(_search_candidates(candidate))
    except Exception as error:
        errors = append_error(errors, "source_discovery", str(error))
    deduped: list[dict[str, object]] = []
    seen: set[str] = set()
    for row in rows:
        url = str(row.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append(row)
    return {
        "source_candidates": deduped[: config.MAX_IDENTITY_SOURCE_CANDIDATES],
        "errors": errors,
        "timings": {"source_discovery": perf_counter() - started},
    }
