"""Tests for Composite Ranking — score aggregation, confidence penalty, motion hints."""

from __future__ import annotations

import pytest

from src.classification.ai_native_classifier import ClassificationResult
from src.extraction.schemas import AINativeLevel, ConfidenceLevel
from src.scoring.composite_ranking import (
    CompositeResult,
    RankedStartup,
    build_ranked_list,
    compute_composite_score,
)
from src.scoring.defensibility_score import DefensibilityScoreResult
from src.scoring.inception_fit_score import InceptionFitScoreResult
from src.scoring.production_readiness import ProductionReadinessResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def high_defensibility() -> DefensibilityScoreResult:
    return DefensibilityScoreResult(
        total_score=80,
        score_breakdown={},
        confidence=ConfidenceLevel.HIGH,
        classification_boost="AI_NATIVE",
        reasoning="Strong defensibility",
        evidence_used=[],
        missing_evidence=[],
    )


@pytest.fixture
def low_defensibility() -> DefensibilityScoreResult:
    return DefensibilityScoreResult(
        total_score=20,
        score_breakdown={},
        confidence=ConfidenceLevel.LOW,
        classification_boost="AI_ASSISTED",
        reasoning="Weak defensibility",
        evidence_used=[],
        missing_evidence=[],
    )


@pytest.fixture
def high_inception_fit() -> InceptionFitScoreResult:
    return InceptionFitScoreResult(
        total_score=80,
        score_breakdown={},
        confidence=ConfidenceLevel.HIGH,
        detected_gaps=[],
        recommended_motion_hint="immediate_outreach",
        reasoning="Strong fit",
        evidence_used=[],
        missing_evidence=[],
    )


@pytest.fixture
def low_inception_fit() -> InceptionFitScoreResult:
    return InceptionFitScoreResult(
        total_score=15,
        score_breakdown={},
        confidence=ConfidenceLevel.LOW,
        detected_gaps=[],
        recommended_motion_hint="lack_evidence_more_research",
        reasoning="Weak fit",
        evidence_used=[],
        missing_evidence=[],
    )


@pytest.fixture
def high_readiness() -> ProductionReadinessResult:
    return ProductionReadinessResult(
        production_readiness_score=85,
        score_breakdown={},
        confidence=ConfidenceLevel.HIGH,
        reasoning="Strong readiness",
        evidence_used=[],
        missing_evidence=[],
    )


@pytest.fixture
def low_readiness() -> ProductionReadinessResult:
    return ProductionReadinessResult(
        production_readiness_score=10,
        score_breakdown={},
        confidence=ConfidenceLevel.LOW,
        reasoning="Weak readiness",
        evidence_used=[],
        missing_evidence=[],
    )


@pytest.fixture
def ai_native_classification() -> ClassificationResult:
    return ClassificationResult(
        startup_name="TestAI",
        classification=AINativeLevel.AI_NATIVE,
        confidence=ConfidenceLevel.HIGH,
        reasoning="AI-native",
        evidence_used=[],
        missing_evidence=[],
    )


@pytest.fixture
def non_ai_classification() -> ClassificationResult:
    return ClassificationResult(
        startup_name="TestNonAI",
        classification=AINativeLevel.NON_AI,
        confidence=ConfidenceLevel.HIGH,
        reasoning="Not AI",
        evidence_used=[],
        missing_evidence=[],
    )


# ---------------------------------------------------------------------------
# Tests for compute_composite_score
# ---------------------------------------------------------------------------


class TestComputeCompositeScore:
    def test_all_present_high_confidence(
        self,
        high_defensibility,
        high_inception_fit,
        high_readiness,
        ai_native_classification,
    ):
        result = compute_composite_score(
            "startup-1",
            high_defensibility,
            high_inception_fit,
            high_readiness,
            ai_native_classification,
        )
        assert isinstance(result, CompositeResult)
        assert result.composite_score >= 50
        assert result.confidence == ConfidenceLevel.HIGH
        assert not result.missing_components
        assert result.defensibility_score == 80
        assert result.inception_fit_score == 80
        assert result.production_readiness_score == 85
        assert result.classification_score == 80

    def test_all_low_confidence(
        self,
        low_defensibility,
        low_inception_fit,
        low_readiness,
        non_ai_classification,
    ):
        result = compute_composite_score(
            "startup-2",
            low_defensibility,
            low_inception_fit,
            low_readiness,
            non_ai_classification,
        )
        assert result.composite_score < 30
        assert result.confidence == ConfidenceLevel.LOW

    def test_missing_components_redistributes_weights(
        self,
        high_defensibility,
        ai_native_classification,
    ):
        result = compute_composite_score(
            "startup-3",
            high_defensibility,
            None,
            None,
            ai_native_classification,
        )
        assert result.composite_score > 0
        assert result.missing_components == ["inception_fit_score", "production_readiness"]
        assert result.confidence == ConfidenceLevel.MEDIUM

    def test_all_missing_returns_zero(self):
        result = compute_composite_score(
            "startup-4",
            None,
            None,
            None,
            None,
        )
        assert result.composite_score == 0.0
        assert result.confidence == ConfidenceLevel.LOW
        assert result.confidence_penalty_applied == 1.0

    def test_score_bounds(
        self,
        high_defensibility,
        high_inception_fit,
        high_readiness,
        ai_native_classification,
    ):
        result = compute_composite_score(
            "startup-5",
            high_defensibility,
            high_inception_fit,
            high_readiness,
            ai_native_classification,
        )
        assert 0 <= result.composite_score <= 100

    def test_confidence_penalty_lowers_score(
        self,
        high_defensibility,
        high_inception_fit,
        high_readiness,
        ai_native_classification,
    ):
        high_conf = compute_composite_score(
            "high",
            high_defensibility,
            high_inception_fit,
            high_readiness,
            ai_native_classification,
        )
        # Now pass missing readiness (penalty applied)
        medium_conf = compute_composite_score(
            "medium",
            high_defensibility,
            high_inception_fit,
            None,
            ai_native_classification,
        )
        assert high_conf.composite_score >= medium_conf.composite_score


# ---------------------------------------------------------------------------
# Tests for build_ranked_list
# ---------------------------------------------------------------------------


class TestBuildRankedList:
    def test_ranking_order(self, high_defensibility, high_inception_fit, high_readiness, ai_native_classification):
        scores = [
            compute_composite_score(
                "a",
                high_defensibility,
                high_inception_fit,
                high_readiness,
                ai_native_classification,
            ),
            compute_composite_score("b", high_defensibility, high_inception_fit, None, ai_native_classification),
        ]
        names = {
            "a": ("Startup A", "HealthTech"),
            "b": ("Startup B", "FinTech"),
        }
        classifications: dict = {}
        ranked = build_ranked_list(scores, names, classifications)
        assert len(ranked) == 2
        assert ranked[0].composite_score >= ranked[1].composite_score

    def test_motion_hints(self, high_defensibility, high_inception_fit, high_readiness):
        def _cls(name: str, level: AINativeLevel) -> ClassificationResult:
            return ClassificationResult(
                startup_name=name,
                classification=level,
                confidence=ConfidenceLevel.HIGH,
                reasoning="",
                evidence_used=[],
                missing_evidence=[],
            )

        ai_native_result = compute_composite_score(
            "native",
            high_defensibility,
            high_inception_fit,
            high_readiness,
            _cls("Native AI", AINativeLevel.AI_NATIVE),
        )
        non_ai_result = compute_composite_score(
            "nonai",
            None,
            None,
            None,
            _cls("Non AI", AINativeLevel.NON_AI),
        )
        names = {
            "native": ("Native AI", "HealthTech"),
            "nonai": ("Non AI", "E-commerce"),
        }
        classifications = {
            "native": _cls("Native AI", AINativeLevel.AI_NATIVE),
            "nonai": _cls("Non AI", AINativeLevel.NON_AI),
        }
        ranked = build_ranked_list([ai_native_result, non_ai_result], names, classifications)
        motion_map = {r.startup_id: r.motion for r in ranked}
        assert motion_map["nonai"] == "not_recommended"

    def test_ranked_startup_schema(
        self, high_defensibility, high_inception_fit, high_readiness, ai_native_classification
    ):
        result = compute_composite_score(
            "s1",
            high_defensibility,
            high_inception_fit,
            high_readiness,
            ai_native_classification,
        )
        names = {"s1": ("S1 Corp", "FinTech")}
        classifications: dict[str, ClassificationResult] = {"s1": ai_native_classification}
        ranked = build_ranked_list([result], names, classifications)
        assert len(ranked) == 1
        rs = ranked[0]
        assert isinstance(rs, RankedStartup)
        assert rs.startup_id == "s1"
        assert rs.startup_name == "S1 Corp"
        assert rs.sector == "FinTech"
        assert 0 <= rs.composite_score <= 100
        assert rs.motion in (
            "immediate_outreach",
            "high_priority_outreach",
            "monitor_and_nurture",
            "lack_evidence_more_research",
            "not_recommended",
        )

    def test_empty_list(self):
        assert build_ranked_list([], {}, {}) == []
