from __future__ import annotations

from src.decisioning.adaptive_recommendation_ranker import rank_recommendations
from src.decisioning.evidence_weighted_scorer import WeightedFeature, score_features
from src.decisioning.uncertainty_estimator import estimate_uncertainty_components


def test_evidence_weighted_scorer_exposes_quantitative_components() -> None:
    result = score_features([
        WeightedFeature(
            name="strong_evidence",
            value=0.9,
            weight=1.0,
            evidence_ids=("e1", "e2"),
            evidence_quality=0.8,
            source_count=2,
        ),
        WeightedFeature(
            name="weak_evidence",
            value=0.3,
            weight=1.0,
            evidence_ids=("e3",),
            evidence_quality=0.4,
            source_count=1,
        ),
    ])

    assert 0.0 <= result["score"] <= 1.0
    assert result["evidence_count"] == 3
    assert result["total_effective_weight"] == 1.2
    assert result["evidence_quality_mean"] == 0.6
    assert "formula" in result


def test_uncertainty_components_decrease_with_more_evidence() -> None:
    sparse = estimate_uncertainty_components(evidence_count=1, source_diversity=1, feature_count=4)
    rich = estimate_uncertainty_components(
        evidence_count=8,
        source_diversity=4,
        feature_count=4,
        evidence_quality=0.9,
    )

    assert rich["uncertainty"] < sparse["uncertainty"]
    assert rich["evidence_coverage"] == 1.0
    assert "formula" in rich


def test_expected_utility_ranking_penalizes_uncertainty_and_low_evidence() -> None:
    ranked = rank_recommendations([
        {
            "recommendation_id": "uncertain",
            "business_impact": 0.9,
            "confidence": 0.8,
            "implementation_complexity": 0.2,
            "risk": 0.1,
            "uncertainty": 0.8,
            "evidence_support": 0.1,
        },
        {
            "recommendation_id": "supported",
            "business_impact": 0.75,
            "confidence": 0.75,
            "implementation_complexity": 0.2,
            "risk": 0.1,
            "uncertainty": 0.1,
            "evidence_support": 0.9,
        },
    ])

    assert ranked[0]["recommendation_id"] == "supported"
    assert ranked[0]["expected_utility"] > ranked[1]["expected_utility"]
    assert "formula" in ranked[0]["expected_utility_breakdown"]
