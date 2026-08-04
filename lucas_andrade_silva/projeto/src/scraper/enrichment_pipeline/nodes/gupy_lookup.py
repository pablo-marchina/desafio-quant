from __future__ import annotations

from urllib.parse import urlsplit

from .. import config
from ..identity import validate_source_identity
from ..signals import AI_KEYWORDS, TECH_KEYWORDS, detect_keyword_hits
from ..state import EnrichmentState
from .llm_summarize import append_error
from .web_scrape import DDGS, _rate_limit, extract_text_from_url


def _search_gupy_candidates(candidate: dict[str, object]) -> list[dict[str, object]]:
    company_name = str(candidate.get("company_name") or candidate.get("nome") or "").strip()
    if not company_name or DDGS is None:
        return []
    rows: list[dict[str, object]] = []
    _rate_limit()
    with DDGS(timeout=config.HTTP_TIMEOUT_SECONDS) as ddgs:
        for result in ddgs.text(f"{company_name} Gupy vagas", max_results=config.MAX_GUPY_PAGES):
            url = str(result.get("href") or result.get("url") or "").strip()
            if "gupy" not in url.casefold():
                continue
            rows.append(
                {
                    "url": url,
                    "source_type": "gupy",
                    "origin": "ddg",
                    "title": str(result.get("title") or "") or None,
                    "snippet": str(result.get("body") or result.get("snippet") or "") or None,
                    "raw_text": None,
                    "metadata": {"host": (urlsplit(url).hostname or "").removeprefix("www.")},
                }
            )
    return rows


def gupy_lookup_node(state: EnrichmentState) -> dict[str, object]:
    if state.get("skip_gupy") or state.get("run_deep_enrichment") is False or ("validated_url" in state and not state.get("validated_url")):
        return {"gupy_profile": state.get("gupy_profile") or {}, "errors": state.get("errors", {})}
    candidate = state.get("candidate", {})
    errors = state.get("errors", {})
    identity_evidence = dict(state.get("identity_evidence") or {})
    sources = list(identity_evidence.get("sources", []))
    best_profile: dict[str, object] = {}
    validated_sources = list(state.get("validated_sources", []))
    try:
        candidates = _search_gupy_candidates(candidate)
    except Exception as error:
        return {"gupy_profile": {}, "errors": append_error(errors, "gupy_lookup", str(error))}

    for source in candidates:
        try:
            source["raw_text"] = extract_text_from_url(str(source.get("url") or ""))[:6000]
        except Exception as error:
            errors = append_error(errors, "gupy_lookup", f"{source.get('url')}: {error}")
            continue
        validation = validate_source_identity(candidate, source)
        sources.append({"url": source.get("url"), "source_type": "gupy", "origin": "ddg", "validation": validation})
        if validation.get("classification") != "MATCH":
            continue
        raw_text = str(source.get("raw_text") or "")
        tech_hits = detect_keyword_hits([raw_text], TECH_KEYWORDS)
        ai_hits = detect_keyword_hits([raw_text], AI_KEYWORDS)
        lines = [line.strip() for line in raw_text.split(".") if line.strip()]
        best_profile = {
            "url": source.get("url"),
            "open_jobs_signals": lines[:8],
            "tech_stack": tech_hits,
            "ai_integrations": ai_hits,
            "validation": validation,
        }
        validated_sources.append({**source, "validation": validation})
        break

    identity_evidence["sources"] = sources
    return {
        "gupy_profile": best_profile,
        "validated_sources": validated_sources,
        "identity_evidence": identity_evidence,
        "errors": errors,
    }
