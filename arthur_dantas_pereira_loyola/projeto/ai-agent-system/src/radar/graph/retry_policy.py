from __future__ import annotations

from radar.graph.state import RadarState


MAX_COLLECTION_ATTEMPTS = 2


def should_retry_collection(state: RadarState) -> bool:
    validation = state.get("validation")
    if validation and validation.has_minimum_evidence:
        return False
    return state.get("collection_attempts", 0) < MAX_COLLECTION_ATTEMPTS


def has_collection_retry_limit_reached(state: RadarState) -> bool:
    validation = state.get("validation")
    if not validation or validation.has_minimum_evidence:
        return False
    return state.get("collection_attempts", 0) >= MAX_COLLECTION_ATTEMPTS
