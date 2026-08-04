"""Thin wrapper over ConfigLoaderService for backward compatibility.

All values previously hardcoded here now live in YAML config files under
``config/`` and are served via ``ConfigLoaderService``.

This module re-exports them at module level so that existing imports like::

    from src.quantitative.params import PRIORITY_SCORE_WEIGHTS

continue to work unchanged.
"""

from __future__ import annotations

from typing import Any

from src.config.loader import ConfigLoaderService

_cfg = ConfigLoaderService()

# =========================================================================
# CONFIDENCE → float mapping
# =========================================================================
CONFIDENCE_FLOAT_MAP: dict[str, float] = _cfg.confidence_float_map()

# =========================================================================
# CONFIDENCE → factor (para scoring com ConfidenceLevel enum)
# =========================================================================
CONFIDENCE_SCORE_FACTORS: dict[str, float] = _cfg.confidence_score_factors()

# =========================================================================
# Confidence thresholds (para classificação high/medium/low)
# =========================================================================
CONFIDENCE_THRESHOLDS: dict[str, float] = _cfg.confidence_thresholds()

# =========================================================================
# Classification → base score
# =========================================================================
CLASSIFICATION_TO_BASE_SCORE: dict[str, float] = (
    _cfg.scoring().classification.base_scores
)

# =========================================================================
# Priority score weights (para recomendações NVIDIA)
# =========================================================================
PRIORITY_SCORE_WEIGHTS: dict[str, float] = _cfg.priority_score_weights()

# =========================================================================
# Opportunity score weights (composite ranking)
# =========================================================================
OPPORTUNITY_SCORE_WEIGHTS: dict[str, float] = (
    _cfg.scoring().opportunity_score.model_dump()
)

# =========================================================================
# Confidence penalty on missing data
# =========================================================================
CONFIDENCE_PENALTY_ON_MISSING: float = _cfg.confidence_penalty_on_missing

# =========================================================================
# Production readiness dimension weights
# =========================================================================
PRODUCTION_READINESS_WEIGHTS: dict[str, float] = (
    _cfg.scoring().production_readiness.model_dump()
)

# =========================================================================
# Defensibility score dimension weights
# =========================================================================
DEFENSIBILITY_WEIGHTS: dict[str, float] = (
    _cfg.scoring().defensibility.model_dump()
)

# =========================================================================
# Inception fit score dimension weights
# =========================================================================
INCEPTION_FIT_WEIGHTS: dict[str, float] = (
    _cfg.scoring().inception_fit.model_dump()
)

# =========================================================================
# AI-native keyword boosts (para detecção de sinais em texto)
# =========================================================================
AI_NATIVE_KEYWORD_BOOSTS: dict[str, float] = (
    _cfg.scoring().keyword_boosts.model_dump()
)

# =========================================================================
# Max signal boost cap
# =========================================================================
MAX_SIGNAL_BOOST: float = _cfg.max_signal_boost

# =========================================================================
# Discovery confidence weights (para calculate_confidence)
# =========================================================================
DISCOVERY_CONFIDENCE_WEIGHTS: dict[str, float] = (
    _cfg.source_quality().discovery["confidence_weights"]
    if "confidence_weights" in _cfg.source_quality().discovery
    else {"has_name": 0.3, "has_website": 0.1, "is_manual_seed": 0.2, "source_reliable": 0.1}
)

# =========================================================================
# Source quality scores (para source_quality_score)
# =========================================================================
SOURCE_QUALITY_SCORES: dict[str, float] = _cfg.source_type_scores()

# =========================================================================
# Gap business impact map
# =========================================================================
GAP_BUSINESS_IMPACT_MAP: dict[str, float] = _cfg.gap_business_impact()

# =========================================================================
# Keyword lists per gap type
# =========================================================================
GAP_KEYWORD_DICT: dict[str, list[str]] = _cfg.gap_keyword_dict()

# =========================================================================
# Knowledge base signal boosts (para detect_ai_native_signals agrupado)
# =========================================================================
_RAW_SIGNAL_BOOSTS: list[dict[str, Any]] = _cfg.knowledge_base_signal_boosts()
KNOWLEDGE_BASE_SIGNAL_BOOSTS: list[tuple[str, str, float]] = [
    (item["pattern"], item["label"], item["boost"]) for item in _RAW_SIGNAL_BOOSTS
]

# =========================================================================
# NVIDIA tech keywords (para has_nvidia_tech)
# =========================================================================
NVIDIA_KEYWORD_BOOSTS: dict[str, float] = _cfg.nvidia_keyword_boosts()

# =========================================================================
# Discovery thresholds
# =========================================================================
DISCOVERY_MAX_SOURCES: int = _cfg.source_quality().discovery.get("max_sources", 10)
MAX_SEARCH_DEPTH: int = _cfg.source_quality().discovery.get("max_search_depth", 2)

# =========================================================================
# Rate limiting (para scraping)
# =========================================================================
DISCOVERY_RATE_LIMIT: dict[str, int] = {
    "requests_per_second": _cfg.source_quality().rate_limit.requests_per_second,
    "concurrent_requests": _cfg.source_quality().rate_limit.concurrent_requests,
}

# =========================================================================
# Workflow thresholds (para agent orchestration)
# =========================================================================
WORKFLOW_THRESHOLDS: dict[str, Any] = _cfg.workflow_thresholds()

# =========================================================================
# Quality gate thresholds
# =========================================================================
QUALITY_GATE_THRESHOLDS: dict[str, Any] = _cfg.quality_gate_thresholds()

# =========================================================================
# Inception fit — no evidence factor
# =========================================================================
NO_EVIDENCE_FACTOR: float = _cfg.no_evidence_factor

# =========================================================================
# Validation
# =========================================================================

_WEIGHT_SETS: dict[str, dict[str, float]] = {
    "PRIORITY_SCORE_WEIGHTS": PRIORITY_SCORE_WEIGHTS,
    "OPPORTUNITY_SCORE_WEIGHTS": OPPORTUNITY_SCORE_WEIGHTS,
    "PRODUCTION_READINESS_WEIGHTS": PRODUCTION_READINESS_WEIGHTS,
    "DEFENSIBILITY_WEIGHTS": DEFENSIBILITY_WEIGHTS,
    "INCEPTION_FIT_WEIGHTS": INCEPTION_FIT_WEIGHTS,
}


def validate_all_weight_sets() -> dict[str, float]:
    """Validate that all weight sets sum to 1.0 (±1e-6 tolerance).

    Returns a dict mapping set name to its sum for inspection.
    """
    results: dict[str, float] = {}
    for name, weights in _WEIGHT_SETS.items():
        total = sum(weights.values())
        results[name] = round(total, 6)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Weight set '{name}' sums to {total}, expected 1.0. Values: {weights}")
    return results
