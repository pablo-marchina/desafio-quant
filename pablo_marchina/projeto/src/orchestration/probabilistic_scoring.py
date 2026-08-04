from __future__ import annotations

from typing import Any

from src.config.loader import ConfigLoaderService
from src.decisioning.evidence_weighted_scorer import WeightedFeature, score_features
from src.decisioning.uncertainty_estimator import estimate_uncertainty_components


def build_probabilistic_score(
    *,
    evidence_items: list[dict[str, Any]],
    startup_profile: dict[str, Any] | None = None,
    classification_label: str = "",
    classification_confidence: float | None = None,
) -> dict[str, Any]:
    features: list[WeightedFeature] = []
    evidence_ids_used: list[str] = []
    missing_metrics: list[str] = []

    for index, ev in enumerate(evidence_items):
        ev_id = str(ev.get("id") or ev.get("evidence_id") or "")
        if ev_id:
            evidence_ids_used.append(ev_id)
        strength, missing = _evidence_strength(ev)
        missing_metrics.extend(f"evidence_{ev_id or index}.{item}" for item in missing)
        features.append(
            WeightedFeature(
                name=f"evidence_{ev_id or index}",
                value=strength,
                weight=1.0,
                evidence_ids=(ev_id,) if ev_id else (),
                evidence_quality=strength,
                source_count=1,
            )
        )

    if classification_confidence is not None:
        bounded = _clamp(classification_confidence)
        features.append(
            WeightedFeature(
                name="ai_classification",
                value=bounded,
                weight=2.0,
                evidence_quality=bounded,
                source_count=1,
            )
        )
    elif startup_profile:
        profile_confidence = _profile_confidence(startup_profile)
        if profile_confidence is None:
            missing_metrics.append("startup_profile.confidence")
        else:
            features.append(
                WeightedFeature(
                    name="profile_confidence",
                    value=profile_confidence,
                    weight=2.0,
                    evidence_quality=profile_confidence,
                    source_count=1,
                )
            )

    if not features:
        return _empty_score(missing_metrics)

    scores = score_features(features)
    evidence_count = len(set(evidence_ids_used))
    source_diversity_count = max(1, len({_source_key(ev) for ev in evidence_items if _source_key(ev)}))
    uncertainty_components = estimate_uncertainty_components(
        evidence_count=evidence_count,
        contradiction_count=0,
        source_diversity=source_diversity_count,
        feature_count=len(features),
        value_variance=float(scores.get("value_variance", 0.0)),
        evidence_quality=float(scores.get("evidence_quality_mean", 1.0)),
    )
    section_scores = _section_scores(float(scores.get("score", 0.0)))
    result = {
        "score": scores.get("score", 0.0),
        "probabilistic_score": scores.get("score", 0.0),
        "confidence": scores.get("confidence", 0.0),
        "uncertainty": uncertainty_components["uncertainty"],
        "uncertainty_components": uncertainty_components,
        "evidence_count": evidence_count,
        "evidence_ids_used": sorted(set(evidence_ids_used)),
        "evidence_coverage": scores.get("evidence_coverage", 0.0),
        "source_diversity": source_diversity_count,
        "evidence_quality_mean": scores.get("evidence_quality_mean", 0.0),
        "value_variance": scores.get("value_variance", 0.0),
        "formula": scores.get("formula", ""),
        "feature_count": len(features),
        "features": scores.get("features", []),
        "missing_metrics": sorted(set(missing_metrics)),
        "sections": section_scores,
        "defensibility": section_scores.get("defensibility", 0.0),
        "inception_fit": section_scores.get("inception_fit", 0.0),
        "production_readiness": section_scores.get("production_readiness", 0.0),
    }
    if classification_label:
        result["classification"] = classification_label
    if classification_confidence is not None:
        result["classification_confidence"] = _clamp(classification_confidence)
    return result


def _evidence_strength(ev: dict[str, Any]) -> tuple[float, list[str]]:
    missing: list[str] = []
    source_reliability = _first_float(
        ev,
        ("source_reliability", "source_quality_score", "source_quality", "reliability"),
    )
    relevance = _first_float(
        ev,
        ("relevance", "relevance_score", "evidence_confidence_score", "confidence_score"),
    )
    if source_reliability is None:
        source_reliability = _confidence_to_float(ev.get("confidence"))
        if source_reliability is None:
            source_reliability = 0.0
            missing.append("source_reliability")
    if relevance is None:
        relevance = _confidence_to_float(ev.get("confidence"))
        if relevance is None:
            relevance = 0.0
            missing.append("relevance")
    return round((_clamp(source_reliability) + _clamp(relevance)) / 2, 4), missing


def _profile_confidence(profile: dict[str, Any]) -> float | None:
    raw = profile.get("confidence") if "confidence" in profile else profile.get("confidence_score")
    if raw is None:
        return None
    if isinstance(raw, str):
        return _confidence_to_float(raw)
    if isinstance(raw, int | float):
        return _clamp(float(raw))
    return None


def _section_scores(base_score: float) -> dict[str, float]:
    cfg = ConfigLoaderService().scoring()
    sections = {
        "defensibility": cfg.defensibility.model_dump(),
        "inception_fit": cfg.inception_fit.model_dump(),
        "production_readiness": cfg.production_readiness.model_dump(),
        "opportunity": cfg.opportunity_score.model_dump(),
    }
    return {
        name: round(_clamp(base_score) * round(sum(weights.values()), 6), 4)
        for name, weights in sections.items()
    }


def _first_float(ev: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = ev.get(key)
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                continue
    return None


def _confidence_to_float(value: object) -> float | None:
    if value is None:
        return None
    raw = getattr(value, "value", value)
    if isinstance(raw, str):
        return {"high": 1.0, "medium": 0.6, "low": 0.3}.get(raw.casefold())
    if isinstance(raw, int | float):
        return _clamp(float(raw))
    return None


def _source_key(ev: dict[str, Any]) -> str:
    return str(ev.get("source") or ev.get("source_id") or ev.get("source_url") or ev.get("url") or "")


def _empty_score(missing_metrics: list[str]) -> dict[str, Any]:
    return {
        "score": 0.0,
        "probabilistic_score": 0.0,
        "confidence": 0.0,
        "uncertainty": 1.0,
        "uncertainty_components": {"uncertainty": 1.0, "formula": "no features available"},
        "evidence_count": 0,
        "evidence_ids_used": [],
        "evidence_coverage": 0.0,
        "source_diversity": 0,
        "evidence_quality_mean": 0.0,
        "value_variance": 1.0,
        "formula": "no features available",
        "feature_count": 0,
        "features": [],
        "missing_metrics": sorted(set(missing_metrics)),
        "sections": _section_scores(0.0),
        "defensibility": 0.0,
        "inception_fit": 0.0,
        "production_readiness": 0.0,
    }


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
