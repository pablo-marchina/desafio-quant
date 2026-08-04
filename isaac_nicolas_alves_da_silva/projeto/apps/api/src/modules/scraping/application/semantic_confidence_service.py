"""Calculo controlado da confianca produzida pela revisao semantica."""

from apps.api.src.modules.scraping.application.dto import (
    SemanticAssessment,
    SemanticValidationResult,
)


class SemanticConfidenceService:
    """Calcula confianca a partir dos fatores estruturados fornecidos pela LLM."""

    contradiction_penalty = 0.30

    def calculate(self, assessment: SemanticAssessment) -> SemanticValidationResult:
        """Aplica os pesos definidos na arquitetura e limita o resultado."""

        confidence = (
            self._bounded(assessment.startup_match_score) * 0.25
            + self._bounded(assessment.evidence_clarity_score) * 0.25
            + self._bounded(assessment.source_reliability_score) * 0.20
            + self._bounded(assessment.statement_specificity_score) * 0.15
            + self._bounded(assessment.context_completeness_score) * 0.15
        )

        if assessment.contradiction_detected:
            confidence -= self.contradiction_penalty

        return SemanticValidationResult(
            assessment=assessment,
            semantic_confidence=round(self._bounded(confidence), 4),
        )

    @staticmethod
    def _bounded(value: float) -> float:
        return max(0.0, min(value, 1.0))
