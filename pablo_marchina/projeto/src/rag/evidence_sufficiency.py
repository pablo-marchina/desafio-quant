"""Evidence sufficiency and abstention assessment for product spikes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from src.rag.counter_evidence import CounterEvidenceRecord
from src.rag.schemas import RetrievedContext

SufficiencyDecision = Literal["proceed", "validate_manually", "abstain"]


class EvidenceSufficiencyConfig(BaseModel):
    enabled: bool = True
    min_required_coverage: float = 0.80
    min_provenance_coverage: float = 0.80
    max_counter_evidence_count_for_proceed: int = 0
    proceed_confidence_floor: float = 0.70
    manual_validation_confidence_cap: float = 0.56
    abstain_confidence_cap: float = 0.42


class EvidenceSufficiencyAssessment(BaseModel):
    decision: SufficiencyDecision
    required_evidence_ids: list[str] = Field(default_factory=list)
    present_evidence_ids: list[str] = Field(default_factory=list)
    missing_evidence_ids: list[str] = Field(default_factory=list)
    counter_evidence_ids: list[str] = Field(default_factory=list)
    required_coverage: float = Field(ge=0.0, le=1.0)
    provenance_coverage: float = Field(ge=0.0, le=1.0)
    original_confidence: float = Field(ge=0.0, le=1.0)
    adjusted_confidence: float = Field(ge=0.0, le=1.0)
    uncertainty: float = Field(ge=0.0, le=1.0)
    missing_evidence: list[str] = Field(default_factory=list)
    degraded_checks: list[dict[str, str | float]] = Field(default_factory=list)
    status: str = "PASS"
    warnings: list[str] = Field(default_factory=list)


def assess_evidence_sufficiency(
    *,
    required_evidence_ids: list[str],
    contexts: list[RetrievedContext],
    baseline_confidence: float,
    counter_evidence: list[CounterEvidenceRecord] | None = None,
    config: EvidenceSufficiencyConfig | None = None,
) -> EvidenceSufficiencyAssessment:
    """Assess whether evidence is sufficient to proceed with a recommendation."""

    resolved = config or EvidenceSufficiencyConfig()
    if not resolved.enabled:
        return EvidenceSufficiencyAssessment(
            decision="proceed",
            required_evidence_ids=required_evidence_ids,
            present_evidence_ids=[context.chunk_id for context in contexts],
            missing_evidence_ids=[],
            counter_evidence_ids=[],
            required_coverage=1.0,
            provenance_coverage=1.0,
            original_confidence=round(baseline_confidence, 4),
            adjusted_confidence=round(baseline_confidence, 4),
            uncertainty=round(1.0 - baseline_confidence, 4),
            status="DISABLED",
            warnings=["evidence_sufficiency_disabled"],
        )

    counter_evidence = counter_evidence or []
    present_ids = _dedupe([context.chunk_id for context in contexts])
    present_required_ids = [evidence_id for evidence_id in required_evidence_ids if evidence_id in set(present_ids)]
    missing_ids = [evidence_id for evidence_id in required_evidence_ids if evidence_id not in set(present_ids)]
    required_coverage = _ratio(len(present_required_ids), len(required_evidence_ids))
    provenance_coverage = _provenance_coverage(contexts)
    counter_ids = [record.evidence_id for record in counter_evidence]
    decision = _decision(required_coverage, provenance_coverage, len(counter_ids), resolved)
    adjusted_confidence = _adjusted_confidence(baseline_confidence, decision, required_coverage, resolved)
    missing_evidence = _missing_evidence(missing_ids, provenance_coverage, counter_ids)
    degraded_checks = _degraded_checks(
        decision=decision,
        required_coverage=required_coverage,
        provenance_coverage=provenance_coverage,
        counter_evidence_count=len(counter_ids),
    )
    return EvidenceSufficiencyAssessment(
        decision=decision,
        required_evidence_ids=required_evidence_ids,
        present_evidence_ids=present_ids,
        missing_evidence_ids=missing_ids,
        counter_evidence_ids=counter_ids,
        required_coverage=round(required_coverage, 4),
        provenance_coverage=round(provenance_coverage, 4),
        original_confidence=round(baseline_confidence, 4),
        adjusted_confidence=adjusted_confidence,
        uncertainty=round(1.0 - adjusted_confidence, 4),
        missing_evidence=missing_evidence,
        degraded_checks=degraded_checks,
    )


def _decision(
    required_coverage: float,
    provenance_coverage: float,
    counter_evidence_count: int,
    config: EvidenceSufficiencyConfig,
) -> SufficiencyDecision:
    if required_coverage == 0.0:
        return "abstain"
    if required_coverage < config.min_required_coverage:
        return "validate_manually"
    if provenance_coverage < config.min_provenance_coverage:
        return "validate_manually"
    if counter_evidence_count > config.max_counter_evidence_count_for_proceed:
        return "validate_manually"
    return "proceed"


def _adjusted_confidence(
    baseline_confidence: float,
    decision: SufficiencyDecision,
    required_coverage: float,
    config: EvidenceSufficiencyConfig,
) -> float:
    if decision == "proceed":
        return round(max(config.proceed_confidence_floor, min(1.0, baseline_confidence)), 4)
    if decision == "abstain":
        return round(min(config.abstain_confidence_cap, baseline_confidence * max(required_coverage, 0.20)), 4)
    return round(min(config.manual_validation_confidence_cap, baseline_confidence * max(required_coverage, 0.50)), 4)


def _missing_evidence(
    missing_ids: list[str],
    provenance_coverage: float,
    counter_ids: list[str],
) -> list[str]:
    items: list[str] = []
    if missing_ids:
        items.append("required RAG evidence not retrieved: " + ", ".join(missing_ids))
    if provenance_coverage < 1.0:
        items.append("complete source provenance for all supporting evidence")
    if counter_ids:
        items.append("manual review of unresolved counter-evidence: " + ", ".join(counter_ids))
    return items


def _degraded_checks(
    *,
    decision: SufficiencyDecision,
    required_coverage: float,
    provenance_coverage: float,
    counter_evidence_count: int,
) -> list[dict[str, str | float]]:
    if decision == "proceed":
        return []
    return [
        {
            "code": "EVIDENCE_SUFFICIENCY_NOT_MET",
            "status": "degraded" if decision == "validate_manually" else "error",
            "decision": decision,
            "required_coverage": round(required_coverage, 4),
            "provenance_coverage": round(provenance_coverage, 4),
            "counter_evidence_count": float(counter_evidence_count),
        }
    ]


def _provenance_coverage(contexts: list[RetrievedContext]) -> float:
    if not contexts:
        return 0.0
    return sum(1 for context in contexts if context.source_id and context.url) / len(contexts)


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 1.0
    return max(0.0, min(1.0, numerator / denominator))


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
