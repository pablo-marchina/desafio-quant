from __future__ import annotations

from src.diagnosis.gap_diagnosis_scoring import diagnose_gaps_quantitative
from src.diagnosis.schemas import GAP_TECH_MAP, GapDiagnosisStatus, GapType
from src.quality.decision_calibration_registry import get_project_decision_inventory


def _evidence(index: int, text: str) -> dict[str, object]:
    return {
        "id": f"ev-{index}",
        "evidence_id": f"ev-{index}",
        "source_id": f"source-{index}",
        "source_url": f"https://source-{index}.example/evidence",
        "text": text,
        "snippet": text,
        "claim": text,
        "confidence": "high",
        "evidence_confidence_score": 0.85,
        "source_quality_score": 0.8,
    }


def test_gap_specific_coverage_compares_raw_ratio_not_normalized_feature() -> None:
    gap_type = GapType.INFERENCE_PERFORMANCE_GAP
    keyword = GAP_TECH_MAP[gap_type][0].value
    evidence = [
        _evidence(1, f"Production stack uses {keyword}."),
        _evidence(2, "Independent company profile."),
        _evidence(3, "Independent product description."),
    ]

    result = diagnose_gaps_quantitative(
        run_id="coverage-ratio",
        evidence_items=evidence,
        accepted_evidence_items=evidence,
        claims=[],
        inventory=get_project_decision_inventory(),
    )
    gap = next(item for item in result.gaps if item.gap_type == gap_type)

    assert gap.thresholds["observed_evidence_coverage"] == 0.3333
    assert gap.production_allowed is True
    assert gap.status != GapDiagnosisStatus.NEEDS_MORE_EVIDENCE


def test_absence_across_three_sources_does_not_invent_an_operational_gap() -> None:
    gap_type = GapType.INFERENCE_PERFORMANCE_GAP
    evidence = [
        _evidence(1, "The company builds artificial intelligence products."),
        _evidence(2, "The product serves enterprise customers."),
        _evidence(3, "The platform automates operational workflows."),
    ]

    result = diagnose_gaps_quantitative(
        run_id="corroborated-absence",
        evidence_items=evidence,
        accepted_evidence_items=evidence,
        claims=[],
        inventory=get_project_decision_inventory(),
    )
    gap = next(item for item in result.gaps if item.gap_type == gap_type)

    assert gap.thresholds["observed_evidence_coverage"] == 0.0
    assert gap.thresholds["corroborated_absence"] == 0.0
    assert gap.production_allowed is False
    assert gap.status == GapDiagnosisStatus.NEEDS_MORE_EVIDENCE
    assert gap.supporting_evidence_ids == []


def test_absence_from_two_sources_remains_blocked() -> None:
    gap_type = GapType.INFERENCE_PERFORMANCE_GAP
    evidence = [
        _evidence(1, "The company builds artificial intelligence products."),
        _evidence(2, "The product serves enterprise customers."),
    ]

    result = diagnose_gaps_quantitative(
        run_id="uncorroborated-absence",
        evidence_items=evidence,
        accepted_evidence_items=evidence,
        claims=[],
        inventory=get_project_decision_inventory(),
    )
    gap = next(item for item in result.gaps if item.gap_type == gap_type)

    assert gap.thresholds["corroborated_absence"] == 0.0
    assert gap.production_allowed is False
    assert gap.status == GapDiagnosisStatus.NEEDS_MORE_EVIDENCE
