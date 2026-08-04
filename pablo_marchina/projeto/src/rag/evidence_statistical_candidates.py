"""Executable statistical evidence-sufficiency candidates."""

from __future__ import annotations

from pydantic import BaseModel, Field

STATISTICAL_EVIDENCE_CANDIDATES: frozenset[str] = frozenset(
    {
        "conformal prediction",
        "conformal risk control",
        "bayesian model averaging",
        "ensemble of evaluators",
        "model disagreement detection",
    }
)


class EvidenceStatisticalCandidateInput(BaseModel):
    required_coverage: float = Field(ge=0.0, le=1.0)
    provenance_coverage: float = Field(ge=0.0, le=1.0)
    baseline_confidence: float = Field(ge=0.0, le=1.0)
    counter_evidence_count: int = Field(default=0, ge=0)
    expected_decision: str


class EvidenceStatisticalCandidateResult(BaseModel):
    candidate_name: str
    implementation_mode: str = "LOCAL_DIRECT_IMPLEMENTATION"
    decision: str
    required_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    provenance_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    adjusted_confidence: float = Field(ge=0.0, le=1.0)
    uncertainty: float = Field(ge=0.0, le=1.0)
    risk_score: float = Field(ge=0.0, le=1.0)
    disagreement_score: float = Field(default=0.0, ge=0.0, le=1.0)
    missing_evidence: list[str] = Field(default_factory=list)
    degraded_checks: list[dict[str, str | float]] = Field(default_factory=list)


def run_statistical_evidence_candidate(
    candidate_name: str,
    item: EvidenceStatisticalCandidateInput,
) -> EvidenceStatisticalCandidateResult:
    if candidate_name == "conformal prediction":
        return _conformal_prediction(candidate_name, item)
    if candidate_name == "conformal risk control":
        return _conformal_risk_control(candidate_name, item)
    if candidate_name == "bayesian model averaging":
        return _bayesian_model_averaging(candidate_name, item)
    if candidate_name == "ensemble of evaluators":
        return _ensemble_of_evaluators(candidate_name, item)
    if candidate_name == "model disagreement detection":
        return _model_disagreement_detection(candidate_name, item)
    return EvidenceStatisticalCandidateResult(
        candidate_name=candidate_name,
        decision="validate_manually",
        adjusted_confidence=0.5,
        uncertainty=0.5,
        risk_score=0.5,
        degraded_checks=[{"code": "UNSUPPORTED_STATISTICAL_CANDIDATE", "status": "degraded"}],
    )


def score_statistical_evidence_output(output: EvidenceStatisticalCandidateResult, *, expected_decision: str) -> float:
    decision_score = 1.0 if output.decision == expected_decision else 0.0
    coverage = output.required_coverage
    provenance = output.provenance_coverage
    expected_confidence = 0.82 if expected_decision == "proceed" else 0.48
    if expected_decision == "abstain":
        expected_confidence = 0.35
    confidence_score = max(0.0, 1.0 - abs(output.adjusted_confidence - expected_confidence))
    missing_score = 1.0 if output.missing_evidence or expected_decision == "proceed" else 0.0
    degraded_score = 1.0 if output.degraded_checks or expected_decision == "proceed" else 0.0
    return round(
        decision_score * 0.30
        + coverage * 0.20
        + provenance * 0.15
        + confidence_score * 0.15
        + missing_score * 0.10
        + degraded_score * 0.10,
        4,
    )


def _conformal_prediction(
    candidate_name: str,
    item: EvidenceStatisticalCandidateInput,
) -> EvidenceStatisticalCandidateResult:
    nonconformity = _nonconformity(item)
    decision = (
        "proceed" if nonconformity <= 0.22 else ("abstain" if item.required_coverage == 0 else "validate_manually")
    )
    confidence = _confidence_for_decision(item, decision, penalty=nonconformity * 0.35)
    return _result(candidate_name, item, decision, confidence, nonconformity)


def _conformal_risk_control(
    candidate_name: str,
    item: EvidenceStatisticalCandidateInput,
) -> EvidenceStatisticalCandidateResult:
    risk = min(1.0, _nonconformity(item) + item.counter_evidence_count * 0.18)
    decision = "proceed" if risk <= 0.18 else ("abstain" if item.required_coverage == 0 else "validate_manually")
    confidence = _confidence_for_decision(item, decision, penalty=risk * 0.45)
    return _result(candidate_name, item, decision, confidence, risk)


def _bayesian_model_averaging(
    candidate_name: str,
    item: EvidenceStatisticalCandidateInput,
) -> EvidenceStatisticalCandidateResult:
    posterior = (
        item.baseline_confidence * 0.45
        + item.required_coverage * 0.25
        + item.provenance_coverage * 0.20
        + max(0.0, 1.0 - item.counter_evidence_count) * 0.10
    )
    decision = "proceed" if posterior >= 0.72 else ("abstain" if item.required_coverage == 0 else "validate_manually")
    confidence = _confidence_for_decision(item, decision, penalty=max(0.0, 0.72 - posterior))
    return _result(candidate_name, item, decision, confidence, max(0.0, 1.0 - posterior))


def _ensemble_of_evaluators(
    candidate_name: str,
    item: EvidenceStatisticalCandidateInput,
) -> EvidenceStatisticalCandidateResult:
    votes = [
        (
            "proceed"
            if item.required_coverage >= 0.8
            else ("abstain" if item.required_coverage == 0 else "validate_manually")
        ),
        "proceed" if item.provenance_coverage >= 0.8 else "validate_manually",
        "proceed" if item.counter_evidence_count == 0 else "validate_manually",
    ]
    decision = max(set(votes), key=votes.count)
    disagreement = 1.0 - votes.count(decision) / len(votes)
    confidence = _confidence_for_decision(item, decision, penalty=disagreement * 0.25)
    return _result(candidate_name, item, decision, confidence, disagreement, disagreement_score=disagreement)


def _model_disagreement_detection(
    candidate_name: str,
    item: EvidenceStatisticalCandidateInput,
) -> EvidenceStatisticalCandidateResult:
    evidence_vote = (
        "proceed" if item.required_coverage >= 0.8 and item.provenance_coverage >= 0.8 else "validate_manually"
    )
    confidence_vote = "proceed" if item.baseline_confidence >= 0.75 else "validate_manually"
    risk_vote = "proceed" if item.counter_evidence_count == 0 else "validate_manually"
    votes = [evidence_vote, confidence_vote, risk_vote]
    decision = max(set(votes), key=votes.count)
    disagreement = 1.0 - votes.count(decision) / len(votes)
    if disagreement > 0.34 and decision == "proceed":
        decision = "validate_manually"
    confidence = _confidence_for_decision(item, decision, penalty=disagreement * 0.35)
    return _result(candidate_name, item, decision, confidence, disagreement, disagreement_score=disagreement)


def _result(
    candidate_name: str,
    item: EvidenceStatisticalCandidateInput,
    decision: str,
    confidence: float,
    risk: float,
    *,
    disagreement_score: float = 0.0,
) -> EvidenceStatisticalCandidateResult:
    missing_evidence = []
    if item.required_coverage < 1.0:
        missing_evidence.append("required evidence coverage below complete support")
    if item.provenance_coverage < 1.0:
        missing_evidence.append("source provenance coverage below complete support")
    degraded = []
    if decision != "proceed":
        degraded.append(
            {
                "code": "STATISTICAL_EVIDENCE_CONTROL_TRIGGERED",
                "status": "degraded" if decision == "validate_manually" else "error",
                "risk_score": round(risk, 4),
            }
        )
    return EvidenceStatisticalCandidateResult(
        candidate_name=candidate_name,
        decision=decision,
        required_coverage=round(item.required_coverage, 4),
        provenance_coverage=round(item.provenance_coverage, 4),
        adjusted_confidence=round(max(0.0, min(1.0, confidence)), 4),
        uncertainty=round(1.0 - max(0.0, min(1.0, confidence)), 4),
        risk_score=round(max(0.0, min(1.0, risk)), 4),
        disagreement_score=round(max(0.0, min(1.0, disagreement_score)), 4),
        missing_evidence=missing_evidence,
        degraded_checks=degraded,
    )


def _nonconformity(item: EvidenceStatisticalCandidateInput) -> float:
    return round(
        min(
            1.0,
            (1.0 - item.required_coverage) * 0.40
            + (1.0 - item.provenance_coverage) * 0.25
            + (1.0 - item.baseline_confidence) * 0.20
            + min(1.0, item.counter_evidence_count) * 0.15,
        ),
        4,
    )


def _confidence_for_decision(
    item: EvidenceStatisticalCandidateInput,
    decision: str,
    *,
    penalty: float,
) -> float:
    if decision == "proceed":
        return max(0.7, item.baseline_confidence - penalty)
    if decision == "abstain":
        return min(0.42, item.baseline_confidence * max(0.2, item.required_coverage) - penalty)
    return min(0.56, item.baseline_confidence * max(0.5, item.required_coverage) - penalty)
