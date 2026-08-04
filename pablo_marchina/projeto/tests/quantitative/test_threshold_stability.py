"""Tests for threshold stability — verify decision boundaries have margin."""

from __future__ import annotations

from src.quantitative.params import (
    CONFIDENCE_THRESHOLDS,
    QUALITY_GATE_THRESHOLDS,
    WORKFLOW_THRESHOLDS,
)


class TestQualityGateThresholds:
    """Verify quality gate thresholds are non-zero and consistent."""

    def test_non_negative(self) -> None:
        for key, value in QUALITY_GATE_THRESHOLDS.items():
            assert isinstance(value, (int, float)), f"{key} must be numeric"
            assert value >= 0, f"{key} must be >= 0"

    def test_blockers_max_is_zero(self) -> None:
        assert QUALITY_GATE_THRESHOLDS["blockers_max"] == 0

    def test_minimums_are_at_least_one(self) -> None:
        for key in ["evidence_items_min", "rag_contexts_min", "recommendations_min"]:
            assert QUALITY_GATE_THRESHOLDS[key] >= 1, f"{key} must be >= 1"


class TestWorkflowThresholds:
    """Verify workflow thresholds are consistent."""

    def test_rag_required(self) -> None:
        assert WORKFLOW_THRESHOLDS["rag_required"] is True

    def test_retries_reasonable(self) -> None:
        max_retries = WORKFLOW_THRESHOLDS["max_evidence_retries"]
        assert 1 <= max_retries <= 10, f"max_evidence_retries={max_retries} out of range"

    def test_minimums_positive(self) -> None:
        for key in ["min_rag_contexts", "min_evidence_items", "min_recommendations", "min_supported_claims"]:
            assert WORKFLOW_THRESHOLDS[key] >= 1, f"{key} must be >= 1"


class TestConfidenceThresholdStability:
    """Verify confidence thresholds have safe margins."""

    def test_threshold_separation(self) -> None:
        gap = CONFIDENCE_THRESHOLDS["high_min"] - CONFIDENCE_THRESHOLDS["medium_min"]
        assert gap >= 0.2, f"gap between high and medium too small: {gap}"

    def test_medium_above_zero(self) -> None:
        assert CONFIDENCE_THRESHOLDS["medium_min"] >= 0.3

    def test_high_below_one(self) -> None:
        assert CONFIDENCE_THRESHOLDS["high_min"] <= 0.9
