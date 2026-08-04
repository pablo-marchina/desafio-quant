from __future__ import annotations

from ..signals import ai_dependency_level, confidence_bucket
from ..state import EnrichmentState


def _legacy_ai_classification(level: str) -> tuple[bool | None, str]:
    if level == "AI_NATIVE":
        return True, "AI_NATIVE"
    if level in {"AI_ENABLED", "AI_MENTIONED"}:
        return True if level == "AI_ENABLED" else None, "AI_ENABLED"
    if level == "NO_SIGNAL":
        return False, "NON_AI"
    return False, "NON_AI"


def ai_classification_node(state: EnrichmentState) -> dict[str, object]:
    if state.get("run_deep_enrichment") is False or ("validated_url" in state and not state.get("validated_url")):
        return {"classification": state.get("classification") or {}}
    texts = list((state.get("web_context") or {}).values())
    github_profile = state.get("github_profile") or {}
    gupy_profile = state.get("gupy_profile") or {}
    texts.extend(str(github_profile.get("description") or ""))
    texts.extend(str(item) for item in gupy_profile.get("open_jobs_signals") or [])
    ai_hits = list(dict.fromkeys(state.get("ai_signals") or []))
    dependency_level = ai_dependency_level(ai_hits, [text for text in texts if text])
    uses_ai_potentially, legacy_classification = _legacy_ai_classification(dependency_level)
    status = "APPROVED" if state.get("validated_url") or state.get("validated_sources") else "REVIEW"
    return {
        "classification": {
            "is_brazilian": True if state.get("identity_confidence_score", 0) >= 50 else None,
            "is_startup": True if state.get("candidate", {}).get("company_name") else None,
            "uses_ai_potentially": uses_ai_potentially,
            "ai_classification": legacy_classification,
            "ai_dependency_level": dependency_level,
            "validation_status": status,
            "rejection_reason": None,
            "llm_confidence": confidence_bucket(state.get("identity_confidence_score")),
            "weight_contributions": {},
            "ai_technology_focus": ", ".join(ai_hits[:3]) or "Unknown",
            "target_market": str(state.get("candidate", {}).get("segment") or "")[:500] or None,
            "key_milestones": None,
        }
    }
