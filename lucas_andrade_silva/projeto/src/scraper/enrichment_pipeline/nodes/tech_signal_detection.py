from __future__ import annotations

from ..signals import AI_KEYWORDS, TECH_KEYWORDS, detect_keyword_hits, summarize_signal_frequency
from ..state import EnrichmentState


def _collect_texts(state: EnrichmentState) -> list[str]:
    texts = list((state.get("web_context") or {}).values())
    github_profile = state.get("github_profile") or {}
    gupy_profile = state.get("gupy_profile") or {}
    if github_profile:
        texts.append(str(github_profile.get("description") or ""))
        texts.extend(
            " ".join(
                part
                for part in (
                    str(repo.get("name") or ""),
                    str(repo.get("description") or ""),
                    str(repo.get("language") or ""),
                    " ".join(str(topic) for topic in repo.get("topics") or []),
                )
                if part
            )
            for repo in github_profile.get("repos") or []
        )
    if gupy_profile:
        texts.extend(str(item) for item in gupy_profile.get("open_jobs_signals") or [])
    return [text for text in texts if text]


def tech_signal_detection_node(state: EnrichmentState) -> dict[str, object]:
    if state.get("run_deep_enrichment") is False or ("validated_url" in state and not state.get("validated_url")):
        return {
            "tech_signals": state.get("tech_signals") or {},
            "ai_signals": state.get("ai_signals") or [],
            "open_jobs_signals": state.get("open_jobs_signals") or [],
            "tech_confidence_score": float(state.get("tech_confidence_score") or 0.0),
        }
    texts = _collect_texts(state)
    tech_stack = detect_keyword_hits(texts, TECH_KEYWORDS)
    ai_integrations = detect_keyword_hits(texts, AI_KEYWORDS)
    github_profile = state.get("github_profile") or {}
    gupy_profile = state.get("gupy_profile") or {}
    tech_stack = sorted(dict.fromkeys([*tech_stack, *(github_profile.get("tech_stack") or []), *(gupy_profile.get("tech_stack") or [])]))
    ai_integrations = sorted(dict.fromkeys([*ai_integrations, *(github_profile.get("ai_integrations") or []), *(gupy_profile.get("ai_integrations") or [])]))
    fontes: dict[str, str] = {item: "scraper_agent" for item in tech_stack}
    for item in github_profile.get("tech_stack") or []:
        if github_profile.get("url"):
            fontes[str(item)] = f"github:{github_profile['url']}"
    open_jobs_signals = list(dict.fromkeys(gupy_profile.get("open_jobs_signals") or []))
    source_count = int(bool(state.get("web_context"))) + int(bool(github_profile)) + int(bool(gupy_profile))
    confidence = min(100.0, float(len(tech_stack) * 8 + len(ai_integrations) * 8 + source_count * 18))
    return {
        "tech_signals": {
            "tech_stack": tech_stack,
            "ai_integrations": ai_integrations,
            "frequencies": {
                "tech_stack": summarize_signal_frequency(tech_stack),
                "ai_integrations": summarize_signal_frequency(ai_integrations),
            },
            "fonte_dados": fontes,
            "github_stack_evidence": list(state.get("github_stack_evidence") or github_profile.get("tech_stack_sources") or []),
        },
        "ai_signals": ai_integrations,
        "open_jobs_signals": open_jobs_signals,
        "tech_confidence_score": confidence,
    }
