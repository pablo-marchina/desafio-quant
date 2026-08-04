"""Sensitivity tests for quantitative parameters.

Verifies that small parameter variations do not cause unstable decision changes.
"""

from __future__ import annotations

import pytest

from src.quantitative.params import (
    CONFIDENCE_THRESHOLDS,
    OPPORTUNITY_SCORE_WEIGHTS,
    PRIORITY_SCORE_WEIGHTS,
)

SENSITIVITY_DELTA = 0.05


def _compute_score(weights: dict[str, float], values: dict[str, float]) -> float:
    return sum(weights.get(k, 0) * v for k, v in values.items())


class TestWeightSensitivity:
    """Verify that small weight changes do not flip decisions."""

    @pytest.fixture
    def sample_scores(self) -> dict[str, float]:
        return {
            "confidence": 0.8,
            "business_impact": 0.6,
            "implementation_complexity_inverse": 0.4,
            "rag_support": 0.7,
            "evidence_support": 0.5,
        }

    def test_priority_score_stability(self, sample_scores: dict[str, float]) -> None:
        base = _compute_score(PRIORITY_SCORE_WEIGHTS, sample_scores)
        for key in PRIORITY_SCORE_WEIGHTS:
            perturbed = dict(PRIORITY_SCORE_WEIGHTS)
            delta = SENSITIVITY_DELTA
            if perturbed[key] - delta > 0:
                perturbed[key] -= delta
                for k in perturbed:
                    if k != key:
                        perturbed[k] += delta / (len(perturbed) - 1)
            perturbed_score = _compute_score(perturbed, sample_scores)
            assert abs(perturbed_score - base) < 0.1, (
                f"Priority score unstable when perturbing {key}: " f"base={base:.4f}, perturbed={perturbed_score:.4f}"
            )

    def test_opportunity_score_stability(self) -> None:
        values = {
            "defensibility": 0.7,
            "inception_fit": 0.6,
            "production_readiness": 0.5,
            "classification": 0.8,
        }
        base = _compute_score(OPPORTUNITY_SCORE_WEIGHTS, values)
        for key in OPPORTUNITY_SCORE_WEIGHTS:
            perturbed = dict(OPPORTUNITY_SCORE_WEIGHTS)
            if perturbed[key] - SENSITIVITY_DELTA > 0:
                perturbed[key] -= SENSITIVITY_DELTA
                for k in perturbed:
                    if k != key:
                        perturbed[k] += SENSITIVITY_DELTA / (len(perturbed) - 1)
            perturbed_score = _compute_score(perturbed, values)
            assert abs(perturbed_score - base) < 0.1, (
                f"Opportunity score unstable when perturbing {key}: "
                f"base={base:.4f}, perturbed={perturbed_score:.4f}"
            )


class TestThresholdStability:
    """Verify that threshold boundaries have margin."""

    def test_confidence_has_margin(self) -> None:
        assert CONFIDENCE_THRESHOLDS["high_min"] > 0.6, "high_min too close to medium"
        assert CONFIDENCE_THRESHOLDS["medium_min"] > 0.3, "medium_min too close to low"
        assert (
            CONFIDENCE_THRESHOLDS["high_min"] - CONFIDENCE_THRESHOLDS["medium_min"]
        ) >= 0.2, "gap between high and medium too small"

    def test_threshold_boundaries(self) -> None:
        high = CONFIDENCE_THRESHOLDS["high_min"]
        medium = CONFIDENCE_THRESHOLDS["medium_min"]
        assert high > medium, "high must be > medium"
        assert medium > 0, "medium must be > 0"


class TestScoreMonotonicity:
    """Verify that scores are monotonic with respect to inputs."""

    def test_priority_score_monotonic(self) -> None:
        base_values = {
            "confidence": 0.5,
            "business_impact": 0.5,
            "implementation_complexity_inverse": 0.5,
            "rag_support": 0.5,
            "evidence_support": 0.5,
        }
        base = _compute_score(PRIORITY_SCORE_WEIGHTS, base_values)
        for key in base_values:
            higher = dict(base_values)
            higher[key] = min(1.0, base_values[key] + 0.2)
            higher_score = _compute_score(PRIORITY_SCORE_WEIGHTS, higher)
            assert higher_score >= base, f"Increasing {key} decreased priority score"
            lower = dict(base_values)
            lower[key] = max(0.0, base_values[key] - 0.2)
            lower_score = _compute_score(PRIORITY_SCORE_WEIGHTS, lower)
            assert lower_score <= base, f"Decreasing {key} increased priority score"


class TestWeightSumValidation:
    """Verify all weight sets sum to 1.0."""

    def test_all_weight_sets_sum_to_one(self) -> None:
        from src.quantitative.params import validate_all_weight_sets

        results = validate_all_weight_sets()
        for name, total in results.items():
            assert abs(total - 1.0) < 1e-6, f"Weight set '{name}' sums to {total}, expected 1.0"
