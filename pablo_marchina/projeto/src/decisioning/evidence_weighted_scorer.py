from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WeightedFeature:
    name: str
    value: float
    weight: float
    evidence_ids: tuple[str, ...] = ()
    evidence_quality: float = 1.0
    source_count: int = 1


def score_features(features: list[WeightedFeature]) -> dict[str, object]:
    scored_features = [_score_feature(item) for item in features]
    total_weight = sum(item["effective_weight"] for item in scored_features)
    if total_weight == 0:
        return {
            "score": 0.0,
            "features": [],
            "confidence": 0.0,
            "uncertainty": 1.0,
            "formula": "sum(value * effective_weight) / sum(effective_weight)",
        }

    weighted = sum(item["bounded_value"] * item["effective_weight"] for item in scored_features)
    score = weighted / total_weight

    unique_evidence = {
        evidence_id
        for feature in features
        for evidence_id in feature.evidence_ids
        if evidence_id
    }
    evidence_count = len(unique_evidence)
    evidence_coverage = min(1.0, evidence_count / max(1, len(features) * 2))
    source_diversity = min(1.0, sum(max(1, item.source_count) for item in features) / max(1, len(features) * 3))
    evidence_quality_mean = sum(item["bounded_quality"] for item in scored_features) / len(scored_features)
    variance = _weighted_variance(scored_features, score, total_weight)
    confidence = _clamp(
        evidence_coverage * 0.45
        + source_diversity * 0.20
        + evidence_quality_mean * 0.25
        + (1.0 - variance) * 0.10
    )
    score = round(weighted / total_weight, 4)
    return {
        "score": score,
        "features": scored_features,
        "confidence": round(confidence, 4),
        "uncertainty": round(1.0 - confidence, 4),
        "evidence_count": evidence_count,
        "evidence_coverage": round(evidence_coverage, 4),
        "source_diversity": round(source_diversity, 4),
        "evidence_quality_mean": round(evidence_quality_mean, 4),
        "value_variance": round(variance, 4),
        "total_effective_weight": round(total_weight, 4),
        "formula": (
            "score=sum(clamp(value,0,1)*max(weight,0)*clamp(evidence_quality,0,1))"
            "/sum(max(weight,0)*clamp(evidence_quality,0,1)); "
            "confidence=0.45*evidence_coverage+0.20*source_diversity"
            "+0.25*evidence_quality_mean+0.10*(1-value_variance)"
        ),
    }


def _score_feature(item: WeightedFeature) -> dict[str, object]:
    bounded_value = _clamp(item.value)
    bounded_quality = _clamp(item.evidence_quality)
    base_weight = max(0.0, item.weight)
    effective_weight = base_weight * bounded_quality
    return {
        "name": item.name,
        "value": item.value,
        "bounded_value": round(bounded_value, 4),
        "weight": item.weight,
        "evidence_quality": item.evidence_quality,
        "bounded_quality": round(bounded_quality, 4),
        "source_count": max(1, item.source_count),
        "effective_weight": round(effective_weight, 4),
        "evidence_ids": item.evidence_ids,
    }


def _weighted_variance(features: list[dict[str, object]], mean: float, total_weight: float) -> float:
    if total_weight <= 0:
        return 1.0
    variance = sum(
        float(item["effective_weight"]) * ((float(item["bounded_value"]) - mean) ** 2)
        for item in features
    ) / total_weight
    return _clamp(variance * 4)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
