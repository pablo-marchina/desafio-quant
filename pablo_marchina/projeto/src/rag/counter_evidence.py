"""Deterministic counter-evidence retrieval for evidence-first product spikes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from src.rag.retrieval import ChunkIndex
from src.rag.schemas import RetrievalQuery, RetrievedContext

CounterEvidenceSeverity = Literal["low", "medium", "high"]


class CounterEvidenceConfig(BaseModel):
    enabled: bool = True
    top_k: int = 4
    require_provenance: bool = True
    confidence_penalty_per_high: float = 0.22
    confidence_penalty_per_medium: float = 0.12
    confidence_penalty_per_low: float = 0.06
    min_confidence: float = 0.30


class CounterEvidenceRecord(BaseModel):
    evidence_id: str
    source_id: str
    title: str
    url: str | None = None
    severity: CounterEvidenceSeverity
    reason: str
    matched_signals: list[str] = Field(default_factory=list)
    relevance_score: float = Field(ge=0.0, le=1.0)


class CounterEvidenceAssessment(BaseModel):
    records: list[CounterEvidenceRecord] = Field(default_factory=list)
    detected_contradiction_ids: list[str] = Field(default_factory=list)
    degraded_checks: list[dict[str, str | float]] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    original_confidence: float = Field(ge=0.0, le=1.0)
    adjusted_confidence: float = Field(ge=0.0, le=1.0)
    uncertainty: float = Field(ge=0.0, le=1.0)
    status: str = "PASS"
    warnings: list[str] = Field(default_factory=list)


_HIGH_SIGNALS = {
    "unsupported": "Source says the capability is unsupported or not validated.",
    "not supported": "Source says the capability is not supported.",
    "deprecated": "Source indicates deprecated behavior.",
    "blocked": "Source indicates a blocking condition.",
    "cannot": "Source states the recommended path cannot satisfy the requirement.",
}
_MEDIUM_SIGNALS = {
    "limitation": "Source describes a limitation.",
    "tradeoff": "Source describes a tradeoff.",
    "requires": "Source adds a requirement that may change feasibility.",
    "manual review": "Source requires manual review.",
    "stale": "Source indicates stale or aging evidence.",
}
_LOW_SIGNALS = {
    "risk": "Source mentions risk.",
    "may": "Source uses uncertain language.",
    "experimental": "Source indicates experimental maturity.",
    "preview": "Source indicates preview maturity.",
}


def retrieve_counter_evidence(
    *,
    claim: str,
    technology: str,
    gap_type: str,
    baseline_confidence: float,
    index: ChunkIndex | None = None,
    contexts: list[RetrievedContext] | None = None,
    config: CounterEvidenceConfig | None = None,
) -> CounterEvidenceAssessment:
    """Find counter-evidence and adjust confidence explicitly."""

    resolved = config or CounterEvidenceConfig()
    if not resolved.enabled:
        return CounterEvidenceAssessment(
            original_confidence=baseline_confidence,
            adjusted_confidence=baseline_confidence,
            uncertainty=round(1.0 - baseline_confidence, 4),
            status="DISABLED",
            warnings=["counter_evidence_disabled"],
        )

    candidate_contexts = _candidate_contexts(
        index=index,
        contexts=contexts,
        technology=technology,
        gap_type=gap_type,
        top_k=resolved.top_k,
    )
    records = [
        record
        for context in candidate_contexts
        if (record := _record_from_context(context, require_provenance=resolved.require_provenance)) is not None
    ]
    records = sorted(
        records,
        key=lambda record: (_severity_rank(record.severity), record.relevance_score),
        reverse=True,
    )
    adjusted_confidence = _adjust_confidence(baseline_confidence, records, resolved)
    degraded_checks = _degraded_checks(records, claim=claim, technology=technology)
    missing_evidence = _missing_evidence(records)
    warnings: list[str] = []
    if resolved.require_provenance and len(records) < len(candidate_contexts):
        warnings.append("counter_evidence_without_required_provenance_dropped")
    return CounterEvidenceAssessment(
        records=records,
        detected_contradiction_ids=[record.evidence_id for record in records],
        degraded_checks=degraded_checks,
        missing_evidence=missing_evidence,
        original_confidence=round(baseline_confidence, 4),
        adjusted_confidence=adjusted_confidence,
        uncertainty=round(1.0 - adjusted_confidence, 4),
        warnings=warnings,
    )


def _candidate_contexts(
    *,
    index: ChunkIndex | None,
    contexts: list[RetrievedContext] | None,
    technology: str,
    gap_type: str,
    top_k: int,
) -> list[RetrievedContext]:
    if contexts is not None:
        return contexts[:top_k]
    if index is None:
        return []
    keywords = [
        technology,
        gap_type,
        "risk",
        "limitation",
        "tradeoff",
        "unsupported",
        "requires",
        "stale",
        "deprecated",
    ]
    return index.retrieve(RetrievalQuery(technology=technology, gap_type=gap_type, keywords=keywords), top_k=top_k)


def _record_from_context(context: RetrievedContext, *, require_provenance: bool) -> CounterEvidenceRecord | None:
    if require_provenance and not (context.source_id and context.url):
        return None
    content = context.content.casefold()
    matched_high = [signal for signal in _HIGH_SIGNALS if signal in content]
    matched_medium = [signal for signal in _MEDIUM_SIGNALS if signal in content]
    matched_low = [signal for signal in _LOW_SIGNALS if signal in content]
    matched = matched_high + matched_medium + matched_low
    if not matched:
        return None
    severity: CounterEvidenceSeverity = "high" if matched_high else ("medium" if matched_medium else "low")
    reason_map = _HIGH_SIGNALS | _MEDIUM_SIGNALS | _LOW_SIGNALS
    return CounterEvidenceRecord(
        evidence_id=context.chunk_id,
        source_id=context.source_id,
        title=context.title,
        url=context.url,
        severity=severity,
        reason=reason_map[matched[0]],
        matched_signals=matched,
        relevance_score=context.relevance_score,
    )


def _adjust_confidence(
    baseline_confidence: float,
    records: list[CounterEvidenceRecord],
    config: CounterEvidenceConfig,
) -> float:
    penalty = 0.0
    for record in records:
        if record.severity == "high":
            penalty += config.confidence_penalty_per_high
        elif record.severity == "medium":
            penalty += config.confidence_penalty_per_medium
        else:
            penalty += config.confidence_penalty_per_low
    return round(max(config.min_confidence, min(1.0, baseline_confidence - penalty)), 4)


def _degraded_checks(
    records: list[CounterEvidenceRecord],
    *,
    claim: str,
    technology: str,
) -> list[dict[str, str | float]]:
    checks: list[dict[str, str | float]] = []
    for record in records:
        checks.append(
            {
                "code": "COUNTER_EVIDENCE_FOUND",
                "status": "degraded" if record.severity in {"medium", "high"} else "warn",
                "severity": record.severity,
                "evidence_id": record.evidence_id,
                "technology": technology,
                "claim": claim,
                "reason": record.reason,
                "relevance_score": record.relevance_score,
            }
        )
    return checks


def _missing_evidence(records: list[CounterEvidenceRecord]) -> list[str]:
    if not records:
        return []
    return [
        "manual review of conflicting RAG evidence",
        "fresh source confirming the recommendation still applies",
        "measured experiment before high-confidence promotion",
    ]


def _severity_rank(severity: CounterEvidenceSeverity) -> int:
    return {"low": 1, "medium": 2, "high": 3}[severity]
