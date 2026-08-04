from __future__ import annotations

from radar.graph.retry_policy import should_retry_collection
from radar.graph.state import RadarState


def route_after_validation(state: RadarState) -> str:
    validation = state.get("validation")
    if validation and validation.has_minimum_evidence:
        return "classifier"
    if should_retry_collection(state):
        return "scraper"
    return "briefing"


def route_after_classification(state: RadarState) -> str:
    classification = state.get("classification")
    if not classification or classification.label == "Non-AI":
        return "briefing"
    return "nvidia_rag"
