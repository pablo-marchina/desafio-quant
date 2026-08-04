from __future__ import annotations

from scripts import run_counter_evidence_product_spike
from src.rag.counter_evidence import CounterEvidenceConfig, retrieve_counter_evidence
from src.rag.schemas import RetrievedContext


def _contexts() -> list[RetrievedContext]:
    return [
        RetrievedContext(
            chunk_id="support",
            source_id="nim",
            title="NIM",
            content="NVIDIA NIM supports production inference endpoints.",
            product="NVIDIA NIM",
            gap_types=["external_api_dependency"],
            url="https://docs.nvidia.com/nim/",
            relevance_score=0.80,
        ),
        RetrievedContext(
            chunk_id="counter",
            source_id="nim_ops",
            title="NIM constraints",
            content="Unsupported regions may block deployment and require manual review.",
            product="NVIDIA NIM",
            gap_types=["external_api_dependency"],
            url="https://docs.nvidia.com/nim/",
            relevance_score=0.86,
        ),
    ]


def test_counter_evidence_adjusts_confidence_and_records_degraded_check() -> None:
    assessment = retrieve_counter_evidence(
        claim="NIM is ready for API replacement.",
        technology="NVIDIA NIM",
        gap_type="external_api_dependency",
        baseline_confidence=0.88,
        contexts=_contexts(),
    )

    assert assessment.detected_contradiction_ids == ["counter"]
    assert assessment.adjusted_confidence < assessment.original_confidence
    assert assessment.uncertainty > 0.20
    assert assessment.degraded_checks[0]["code"] == "COUNTER_EVIDENCE_FOUND"
    assert assessment.missing_evidence


def test_counter_evidence_can_be_disabled_without_changing_confidence() -> None:
    assessment = retrieve_counter_evidence(
        claim="NIM is ready for API replacement.",
        technology="NVIDIA NIM",
        gap_type="external_api_dependency",
        baseline_confidence=0.88,
        contexts=_contexts(),
        config=CounterEvidenceConfig(enabled=False),
    )

    assert assessment.status == "DISABLED"
    assert assessment.adjusted_confidence == 0.88
    assert assessment.detected_contradiction_ids == []


def test_counter_evidence_drops_unprovenanced_records_when_required() -> None:
    context = RetrievedContext(
        chunk_id="counter_no_url",
        source_id="nim_ops",
        title="NIM constraints",
        content="Unsupported regions may block deployment.",
        product="NVIDIA NIM",
        gap_types=["external_api_dependency"],
        relevance_score=0.86,
    )

    assessment = retrieve_counter_evidence(
        claim="NIM is ready for API replacement.",
        technology="NVIDIA NIM",
        gap_type="external_api_dependency",
        baseline_confidence=0.88,
        contexts=[context],
    )

    assert assessment.records == []
    assert "counter_evidence_without_required_provenance_dropped" in assessment.warnings


def test_counter_evidence_product_spike_report_promotes_product_spike() -> None:
    report = run_counter_evidence_product_spike.build_report(min_delta=0.12)

    assert report["decision"] == "PROMOTE_TO_PRODUCT_SPIKE"
    assert report["quality_delta"] >= 0.12
    assert report["regression_count"] == 0
    assert report["case_count"] == 2
