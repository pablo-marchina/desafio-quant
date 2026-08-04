"""Final log aggregation node."""

from __future__ import annotations

from collections import Counter
from typing import Any

from ..state import EnrichmentState


def _source_errors(errors: object) -> Counter[str]:
    if isinstance(errors, dict):
        counter: Counter[str] = Counter()
        for source, messages in errors.items():
            if isinstance(messages, list):
                counter[str(source)] += len(messages)
            elif messages:
                counter[str(source)] += 1
        return counter
    return Counter(error.split(":", 2)[0] if ":" in error else error for error in (errors or []))


def summarize_result(state: EnrichmentState) -> dict[str, Any]:
    classification = state.get("classification", {})
    status = classification.get("validation_status") or "REVIEW"
    ai = classification.get("ai_classification") or "NON_AI"
    confidence = classification.get("llm_confidence") or "L"
    identity = str((state.get("identity_validation") or {}).get("classification") or "INSUFFICIENT_EVIDENCE")
    enrichment_status = str(state.get("enrichment_status") or "needs_review")
    source_errors = _source_errors(state.get("errors", {}))
    review_reason = "approved"
    if status == "REVIEW":
        if identity in {"POSSIBLE_MATCH", "INSUFFICIENT_EVIDENCE"}:
            review_reason = "low_identity_confidence"
        elif not state.get("company_description"):
            review_reason = "no_valid_description_source"
        elif not (state.get("tech_signals", {}).get("tech_stack") or state.get("tech_signals", {}).get("ai_integrations")):
            review_reason = "no_tech_evidence"
        else:
            review_reason = "possible_homonym"
    elif status == "REJECTED":
        review_reason = "source_error" if state.get("errors") else "possible_homonym"
    elif status == "DISCARDED":
        review_reason = "no_valid_source_found_after_10_urls"
    return {
        "total": 1,
        "APPROVED": int(status == "APPROVED"),
        "REVIEW": int(status == "REVIEW"),
        "REJECTED": int(status == "REJECTED"),
        "DISCARDED": int(status == "DISCARDED"),
        "AI_NATIVE": int(ai == "AI_NATIVE"),
        "AI_ENABLED": int(ai == "AI_ENABLED"),
        "NON_AI": int(ai == "NON_AI"),
        "MATCH": int(identity == "MATCH"),
        "POSSIBLE_MATCH": int(identity == "POSSIBLE_MATCH"),
        "WRONG_COMPANY": int(identity == "WRONG_COMPANY"),
        "INSUFFICIENT_EVIDENCE": int(identity == "INSUFFICIENT_EVIDENCE"),
        "enriched": int(enrichment_status == "enriched"),
        "needs_review": int(enrichment_status == "needs_review"),
        "insufficient_evidence": int(enrichment_status == "insufficient_evidence"),
        "error": int(enrichment_status == "error"),
        "confidence": confidence,
        "confidence_H": int(confidence == "H"),
        "confidence_M": int(confidence == "M"),
        "confidence_L": int(confidence == "L"),
        "errors_by_source": dict(source_errors),
        "updated": bool(state.get("updated")),
        "review_reason": review_reason,
        "validated_url": str(state.get("validated_url") or state.get("best_url") or ""),
        "final_reason": str(state.get("final_reason") or classification.get("rejection_reason") or ""),
        "ai_dependency_level": str(classification.get("ai_dependency_level") or "INSUFFICIENT_EVIDENCE"),
        "tech_stack": list((state.get("tech_signals") or {}).get("tech_stack") or []),
    }


def log_result_node(state: EnrichmentState) -> dict[str, Any]:
    return {"log_summary": summarize_result(state)}
