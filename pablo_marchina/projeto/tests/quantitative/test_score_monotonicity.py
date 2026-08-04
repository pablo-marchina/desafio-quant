"""Tests for score monotonicity — verify scores behave as expected."""

from __future__ import annotations

import pytest

from src.quantitative.params import (
    DEFENSIBILITY_WEIGHTS,
    INCEPTION_FIT_WEIGHTS,
    PRODUCTION_READINESS_WEIGHTS,
)


def _compute_score(weights: dict[str, float], values: dict[str, float]) -> float:
    return sum(weights.get(k, 0) * v for k, v in values.items())


class TestDefensibilityMonotonicity:
    """Verify defensibility score increases with each dimension."""

    @pytest.fixture
    def base_values(self) -> dict[str, float]:
        return {k: 0.5 for k in DEFENSIBILITY_WEIGHTS}

    def test_all_dimensions_positive_contribution(self, base_values: dict[str, float]) -> None:
        base = _compute_score(DEFENSIBILITY_WEIGHTS, base_values)
        for key in DEFENSIBILITY_WEIGHTS:
            improved = dict(base_values)
            improved[key] = 1.0
            improved_score = _compute_score(DEFENSIBILITY_WEIGHTS, improved)
            assert improved_score > base, f"Increasing {key} did not improve score"

    def test_all_dimensions_negative_contribution(self, base_values: dict[str, float]) -> None:
        base = _compute_score(DEFENSIBILITY_WEIGHTS, base_values)
        for key in DEFENSIBILITY_WEIGHTS:
            worsened = dict(base_values)
            worsened[key] = 0.0
            worsened_score = _compute_score(DEFENSIBILITY_WEIGHTS, worsened)
            assert worsened_score < base, f"Decreasing {key} did not reduce score"


class TestInceptionFitMonotonicity:
    """Verify inception fit score increases with each dimension."""

    def test_monotonic_increases(self) -> None:
        values = {k: 0.5 for k in INCEPTION_FIT_WEIGHTS}
        base = _compute_score(INCEPTION_FIT_WEIGHTS, values)
        for key in INCEPTION_FIT_WEIGHTS:
            higher = dict(values)
            higher[key] = 1.0
            assert _compute_score(INCEPTION_FIT_WEIGHTS, higher) > base


class TestProductionReadinessMonotonicity:
    """Verify production readiness score increases with each dimension."""

    def test_monotonic_increases(self) -> None:
        values = {k: 0.5 for k in PRODUCTION_READINESS_WEIGHTS}
        base = _compute_score(PRODUCTION_READINESS_WEIGHTS, values)
        for key in PRODUCTION_READINESS_WEIGHTS:
            higher = dict(values)
            higher[key] = 1.0
            assert _compute_score(PRODUCTION_READINESS_WEIGHTS, higher) > base
