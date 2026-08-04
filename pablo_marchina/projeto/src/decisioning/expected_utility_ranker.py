from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UtilityCandidate:
    candidate_id: str
    expected_value: float
    confidence: float
    implementation_complexity: float
    risk: float = 0.0
    uncertainty: float = 0.0
    evidence_support: float = 0.0


def expected_utility(candidate: UtilityCandidate) -> float:
    return float(expected_utility_breakdown(candidate)["expected_utility"])


def expected_utility_breakdown(candidate: UtilityCandidate) -> dict[str, float | str]:
    expected_value = _clamp(candidate.expected_value)
    confidence = _clamp(candidate.confidence)
    complexity = _clamp(candidate.implementation_complexity)
    risk = _clamp(candidate.risk)
    uncertainty = _clamp(candidate.uncertainty)
    evidence_support = _clamp(candidate.evidence_support)
    evidence_multiplier = 0.5 + (evidence_support * 0.5)
    value_component = expected_value * confidence * (1.0 - uncertainty) * evidence_multiplier
    cost_component = (complexity + risk) / 2
    utility = _clamp(value_component - cost_component)
    return {
        "expected_utility": round(utility, 4),
        "value_component": round(value_component, 4),
        "cost_component": round(cost_component, 4),
        "expected_value": round(expected_value, 4),
        "confidence": round(confidence, 4),
        "implementation_complexity": round(complexity, 4),
        "risk": round(risk, 4),
        "uncertainty": round(uncertainty, 4),
        "evidence_support": round(evidence_support, 4),
        "formula": (
            "utility=clamp(expected_value*confidence*(1-uncertainty)"
            "*(0.5+0.5*evidence_support)-mean(complexity,risk))"
        ),
    }


def rank_by_expected_utility(candidates: list[UtilityCandidate]) -> list[UtilityCandidate]:
    return sorted(candidates, key=expected_utility, reverse=True)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
