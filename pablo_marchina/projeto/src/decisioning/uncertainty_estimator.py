from __future__ import annotations


def estimate_uncertainty(
    *,
    evidence_count: int,
    contradiction_count: int = 0,
    source_diversity: int = 1,
    feature_count: int | None = None,
    value_variance: float = 0.0,
    evidence_quality: float = 1.0,
) -> float:
    return float(estimate_uncertainty_components(
        evidence_count=evidence_count,
        contradiction_count=contradiction_count,
        source_diversity=source_diversity,
        feature_count=feature_count,
        value_variance=value_variance,
        evidence_quality=evidence_quality,
    )["uncertainty"])


def estimate_uncertainty_components(
    *,
    evidence_count: int,
    contradiction_count: int = 0,
    source_diversity: int = 1,
    feature_count: int | None = None,
    value_variance: float = 0.0,
    evidence_quality: float = 1.0,
) -> dict[str, float | str]:
    feature_target = max(1, feature_count or 3)
    evidence_target = max(2, feature_target * 2)
    diversity_target = max(2, min(5, feature_target))
    evidence_coverage = _clamp(evidence_count / evidence_target)
    diversity_coverage = _clamp(source_diversity / diversity_target)
    contradiction_ratio = _clamp(contradiction_count / max(1, evidence_count))
    quality_gap = 1.0 - _clamp(evidence_quality)
    variance = _clamp(value_variance)
    uncertainty = _clamp(
        0.40 * (1.0 - evidence_coverage)
        + 0.20 * (1.0 - diversity_coverage)
        + 0.20 * contradiction_ratio
        + 0.10 * variance
        + 0.10 * quality_gap
    )
    return {
        "uncertainty": round(uncertainty, 4),
        "evidence_coverage": round(evidence_coverage, 4),
        "source_diversity_coverage": round(diversity_coverage, 4),
        "contradiction_ratio": round(contradiction_ratio, 4),
        "value_variance": round(variance, 4),
        "evidence_quality_gap": round(quality_gap, 4),
        "evidence_target": float(evidence_target),
        "diversity_target": float(diversity_target),
        "formula": (
            "uncertainty=0.40*(1-evidence_coverage)+0.20*(1-source_diversity_coverage)"
            "+0.20*contradiction_ratio+0.10*value_variance+0.10*evidence_quality_gap"
        ),
    }


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
