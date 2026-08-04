from __future__ import annotations

from .. import config
from ..state import EnrichmentState
from .llm_summarize import append_error
from .web_scrape import extract_text_from_url


def web_context_lookup_node(state: EnrichmentState) -> dict[str, object]:
    if state.get("run_deep_enrichment") is False or state.get("skip_description") or ("validated_url" in state and not state.get("validated_url")):
        return {
            "raw_texts": state.get("raw_texts") or {},
            "web_context": state.get("web_context") or {},
            "evidence_urls": state.get("evidence_urls") or [],
            "errors": state.get("errors", {}),
        }
    errors = state.get("errors", {})
    raw_texts: dict[str, str] = {}
    evidence_urls: list[str] = []
    for source in state.get("validated_sources", []):
        validation = source.get("validation") or {}
        if validation.get("classification") != "MATCH":
            continue
        source_type = str(source.get("source_type") or "")
        if source_type in {"github", "gupy"}:
            continue
        url = str(source.get("url") or "")
        text = str(source.get("raw_text") or "")
        if not text:
            try:
                text = extract_text_from_url(url)
            except Exception as error:
                errors = append_error(errors, "web_context_lookup", f"{url}: {error}")
                continue
        if len(text.strip()) < 200:
            continue
        raw_texts[url] = text[:6000]
        evidence_urls.append(url)
        if len(evidence_urls) >= config.MAX_EVIDENCE_PAGES:
            break
    return {
        "raw_texts": raw_texts,
        "web_context": raw_texts,
        "evidence_urls": list(dict.fromkeys([*state.get("evidence_urls", []), *evidence_urls])),
        "errors": errors,
    }
