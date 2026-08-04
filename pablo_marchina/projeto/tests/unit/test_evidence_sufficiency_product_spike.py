from __future__ import annotations

from scripts import run_evidence_sufficiency_product_spike
from src.rag.counter_evidence import CounterEvidenceRecord
from src.rag.evidence_sufficiency import EvidenceSufficiencyConfig, assess_evidence_sufficiency
from src.rag.schemas import RetrievedContext


def _context(chunk_id: str) -> RetrievedContext:
    return RetrievedContext(
        chunk_id=chunk_id,
        source_id=chunk_id,
        title=chunk_id,
        content="NVIDIA evidence.",
        product="NVIDIA",
        gap_types=["high_latency"],
        url="https://docs.nvidia.com/",
        relevance_score=0.80,
    )


def test_evidence_sufficiency_validates_manually_when_required_evidence_missing() -> None:
    assessment = assess_evidence_sufficiency(
        required_evidence_ids=["a", "b"],
        contexts=[_context("a")],
        baseline_confidence=0.86,
    )

    assert assessment.decision == "validate_manually"
    assert assessment.required_coverage == 0.5
    assert assessment.missing_evidence_ids == ["b"]
    assert assessment.adjusted_confidence <= 0.56
    assert assessment.degraded_checks


def test_evidence_sufficiency_abstains_when_no_required_evidence_present() -> None:
    assessment = assess_evidence_sufficiency(
        required_evidence_ids=["a"],
        contexts=[],
        baseline_confidence=0.74,
    )

    assert assessment.decision == "abstain"
    assert assessment.adjusted_confidence <= 0.42
    assert assessment.uncertainty >= 0.58


def test_evidence_sufficiency_counter_evidence_forces_manual_validation() -> None:
    counter = CounterEvidenceRecord(
        evidence_id="counter",
        source_id="source",
        title="Counter",
        url="https://docs.nvidia.com/",
        severity="medium",
        reason="Source requires manual review.",
        matched_signals=["manual review"],
        relevance_score=0.82,
    )

    assessment = assess_evidence_sufficiency(
        required_evidence_ids=["a"],
        contexts=[_context("a")],
        baseline_confidence=0.88,
        counter_evidence=[counter],
    )

    assert assessment.decision == "validate_manually"
    assert assessment.counter_evidence_ids == ["counter"]
    assert "manual review of unresolved counter-evidence: counter" in assessment.missing_evidence


def test_evidence_sufficiency_can_be_disabled() -> None:
    assessment = assess_evidence_sufficiency(
        required_evidence_ids=["a"],
        contexts=[],
        baseline_confidence=0.74,
        config=EvidenceSufficiencyConfig(enabled=False),
    )

    assert assessment.status == "DISABLED"
    assert assessment.decision == "proceed"
    assert assessment.adjusted_confidence == 0.74


def test_evidence_sufficiency_product_spike_report_promotes_product_spike() -> None:
    report = run_evidence_sufficiency_product_spike.build_report(min_delta=0.08)

    assert report["decision"] == "PROMOTE_TO_PRODUCT_SPIKE"
    assert report["quality_delta"] >= 0.08
    assert report["regression_count"] == 0
    assert report["case_count"] == 3
