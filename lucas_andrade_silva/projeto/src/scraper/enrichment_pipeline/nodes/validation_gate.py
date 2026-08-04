from __future__ import annotations

from .. import config
from ..signals import confidence_bucket
from ..state import EnrichmentState


def validation_gate_node(state: EnrichmentState) -> dict[str, object]:
    validated_url = str(state.get("validated_url") or "") or None
    identity_validation = state.get("identity_validation") or {}
    confidence = float(identity_validation.get("confidence") or state.get("identity_confidence_score") or 0.0)
    rejected_urls = list(dict.fromkeys(state.get("rejected_urls", []) or []))
    attempts = list(state.get("candidate_attempts", []) or [])
    first_possible = next(
        (
            attempt.get("url")
            for attempt in attempts
            if str(attempt.get("classification") or "") == "POSSIBLE_MATCH" and int(attempt.get("confidence") or 0) < config.IDENTITY_APPROVAL_THRESHOLD
        ),
        None,
    )
    if validated_url:
        final_status = "APPROVED"
        enrichment_status = "enriched" if state.get("company_description") else "needs_review"
        final_reason = "validated_url accepted"
        discard_reason = None
        is_active = True
        classification_name = "MATCH"
    else:
        if state.get("discard_reason"):
            final_status = "DISCARDED"
            enrichment_status = "discarded"
            final_reason = str(state.get("discard_reason"))
            discard_reason = str(state.get("discard_reason"))
            is_active = False
            classification_name = "INSUFFICIENT_EVIDENCE"
        else:
            final_status = "REVIEW"
            enrichment_status = "needs_review"
            final_reason = "no reliable company-specific source found"
            discard_reason = None
            is_active = True
            classification_name = str(identity_validation.get("classification") or "INSUFFICIENT_EVIDENCE")

    return {
        "classification": {
            **state.get("classification", {}),
            "description": state.get("company_description") or None,
            "evidence_text": state.get("company_description") or None,
            "validation_status": final_status,
            "rejection_reason": final_reason if final_status in {"REJECTED", "DISCARDED"} else None,
            "llm_confidence": confidence_bucket(confidence),
        },
        "identity_validation": {
            **identity_validation,
            "classification": classification_name,
            "confidence": confidence,
        },
        "identity_evidence": {
            **(state.get("identity_evidence") or {}),
            "validated_urls": [validated_url] if validated_url else [],
            "candidate_urls": [str(item.get("url") or "") for item in attempts if item.get("url")],
            "rejected_urls": rejected_urls,
            "candidate_attempts": attempts,
        },
        "identity_confidence_score": confidence,
        "enrichment_status": enrichment_status,
        "website_candidate": None if validated_url else first_possible,
        "best_url_confirmed": validated_url,
        "best_url": validated_url,
        "validated_url": validated_url,
        "validated_urls": [validated_url] if validated_url else [],
        "candidate_urls": [str(item.get("url") or "") for item in attempts if item.get("url")],
        "candidate_urls_evaluated": attempts,
        "rejected_urls": rejected_urls,
        "final_status": final_status,
        "final_reason": final_reason,
        "discard_reason": discard_reason,
        "is_active": is_active,
        "selected_website": validated_url,
        "selected_linkedin": None,
    }
