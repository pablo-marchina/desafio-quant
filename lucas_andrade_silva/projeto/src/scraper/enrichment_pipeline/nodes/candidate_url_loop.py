from __future__ import annotations

from copy import deepcopy
from time import perf_counter

from .. import config
from ..identity import validate_source_identity
from ..state import EnrichmentState
from .llm_summarize import append_error
from .web_scrape import _is_low_value_url, extract_text_from_url


def _validate_candidate_source(candidate: dict[str, object], source: dict[str, object]) -> dict[str, object]:
    enriched = deepcopy(source)
    raw_text = str(enriched.get("raw_text") or "")
    if not raw_text and not _is_low_value_url(str(enriched.get("url") or "")):
        try:
            raw_text = extract_text_from_url(str(enriched.get("url") or ""))
        except Exception:
            raw_text = ""
    if raw_text:
        enriched["raw_text"] = raw_text[:6000]
    validation = validate_source_identity(candidate, enriched)
    enriched["validation"] = validation
    return enriched


def candidate_url_loop_node(state: EnrichmentState) -> dict[str, object]:
    if state.get("run_deep_only"):
        validated_source = state.get("validated_source")
        validated_url = str(state.get("validated_url") or "")
        if not validated_source and validated_url:
            validated_source = {
                "url": validated_url,
                "source_type": "website",
                "origin": "persisted",
                "validation": {
                    "classification": "MATCH",
                    "confidence": int(state.get("identity_confidence_score") or config.IDENTITY_MATCH_THRESHOLD),
                    "reason": "persisted validated url",
                    "matched_signals": [],
                    "negative_signals": [],
                    "should_update_database": True,
                },
            }
        return {
            "validated_source": validated_source,
            "validated_sources": [validated_source] if validated_source else list(state.get("validated_sources", [])),
            "validated_url": validated_url or None,
            "candidate_attempts": list(state.get("candidate_attempts", [])),
            "rejected_sources": list(state.get("rejected_sources", [])),
            "rejected_urls": list(state.get("rejected_urls", [])),
            "identity_validation": state.get("identity_validation") or {},
            "identity_evidence": state.get("identity_evidence") or {},
            "identity_confidence_score": float(state.get("identity_confidence_score") or 0.0),
            "enrichment_status": state.get("enrichment_status") or "needs_review",
            "is_active": state.get("is_active", True),
            "discard_reason": state.get("discard_reason"),
        }

    candidate = state.get("candidate", {})
    errors = state.get("errors", {})
    started = perf_counter()
    validated_source: dict[str, object] | None = None
    validated_sources: list[dict[str, object]] = []
    rejected_sources: list[dict[str, object]] = []
    rejected_urls: list[str] = []
    candidate_attempts: list[dict[str, object]] = []
    evidence: list[dict[str, object]] = []
    website_candidate: str | None = None
    best_confidence = 0

    for url_index, source in enumerate(state.get("source_candidates", [])[: config.MAX_IDENTITY_SOURCE_CANDIDATES], start=1):
        try:
            enriched = _validate_candidate_source(candidate, source)
        except Exception as error:
            errors = append_error(errors, "candidate_url_loop", f"{source.get('url')}: {error}")
            continue
        validation = enriched.get("validation") or {}
        classification = str(validation.get("classification") or "INSUFFICIENT_EVIDENCE")
        confidence = int(validation.get("confidence") or 0)
        best_confidence = max(best_confidence, confidence)
        decision = "continue"
        if classification == "MATCH" and confidence >= config.IDENTITY_MATCH_THRESHOLD:
            validated_source = enriched
            validated_sources = [enriched]
            decision = "accepted"
        elif classification == "WRONG_COMPANY":
            rejected_sources.append(enriched)
            rejected_urls.append(f"{enriched.get('url')} | {validation.get('reason') or 'wrong company'}")
            decision = "rejected"
        elif classification == "POSSIBLE_MATCH" and not website_candidate:
            website_candidate = str(enriched.get("url") or "") or None
        candidate_attempts.append(
            {
                "url_index": url_index,
                "url": str(enriched.get("url") or ""),
                "classification": classification,
                "confidence": confidence,
                "reason": str(validation.get("reason") or ""),
                "decision": decision,
                "matched_signals": list(validation.get("matched_signals") or []),
                "negative_signals": list(validation.get("negative_signals") or []),
            }
        )
        evidence.append(
            {
                "url": enriched.get("url"),
                "source_type": enriched.get("source_type"),
                "origin": enriched.get("origin"),
                "validation": validation,
            }
        )
        if validated_source:
            break

    if validated_source:
        identity_validation = dict(validated_source.get("validation") or {})
        enrichment_status = "enriched"
        is_active = True
        discard_reason = None
    else:
        identity_validation = {
            "classification": "INSUFFICIENT_EVIDENCE",
            "confidence": best_confidence,
            "reason": "no reliable company-specific source found",
            "matched_signals": [],
            "negative_signals": [],
            "should_update_database": False,
        }
        enrichment_status = "discarded"
        is_active = False
        discard_reason = "no_valid_source_found_after_10_urls"

    return {
        "candidate_urls_queue": list(state.get("source_candidates", [])[: config.MAX_IDENTITY_SOURCE_CANDIDATES]),
        "candidate_attempts": candidate_attempts,
        "validated_source": validated_source,
        "validated_sources": validated_sources,
        "validated_url": str((validated_source or {}).get("url") or "") or None,
        "rejected_sources": rejected_sources,
        "rejected_urls": rejected_urls,
        "identity_validation": identity_validation,
        "identity_evidence": {"sources": evidence},
        "identity_confidence_score": float(best_confidence),
        "website_candidate": website_candidate,
        "enrichment_status": enrichment_status,
        "is_active": is_active,
        "discard_reason": discard_reason,
        "errors": errors,
        "timings": {"candidate_url_loop": perf_counter() - started},
    }
