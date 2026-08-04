"""Testes do calculo de confianca semantica controlado pelo sistema."""

from apps.api.src.modules.scraping.application.dto import SemanticAssessment
from apps.api.src.modules.scraping.application.semantic_confidence_service import (
    SemanticConfidenceService,
)
from apps.api.src.modules.scraping.domain.enums import SemanticReviewDecision


def make_assessment(*, contradiction_detected: bool = False) -> SemanticAssessment:
    return SemanticAssessment(
        startup_match_score=0.90,
        evidence_clarity_score=0.80,
        source_reliability_score=0.70,
        statement_specificity_score=0.60,
        context_completeness_score=0.50,
        contradiction_detected=contradiction_detected,
        decision=SemanticReviewDecision.ACCEPTED,
        reason="Evidencia suficiente.",
    )


def test_calculates_confidence_from_separate_factors() -> None:
    result = SemanticConfidenceService().calculate(make_assessment())

    assert result.semantic_confidence == 0.73


def test_contradiction_reduces_confidence() -> None:
    result = SemanticConfidenceService().calculate(
        make_assessment(contradiction_detected=True)
    )

    assert result.semantic_confidence == 0.43


def test_limits_invalid_factor_values() -> None:
    assessment = SemanticAssessment(
        startup_match_score=2.0,
        evidence_clarity_score=2.0,
        source_reliability_score=2.0,
        statement_specificity_score=2.0,
        context_completeness_score=2.0,
        contradiction_detected=False,
        decision=SemanticReviewDecision.ACCEPTED,
        reason="Valores devem ser limitados.",
    )

    result = SemanticConfidenceService().calculate(assessment)

    assert result.semantic_confidence == 1.0
