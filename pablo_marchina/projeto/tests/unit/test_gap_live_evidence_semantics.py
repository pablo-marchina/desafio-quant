from __future__ import annotations

from src.diagnosis.gap_diagnosis_scoring import diagnose_gaps_quantitative
from src.diagnosis.schemas import GapDiagnosisStatus, GapType


def test_natural_quote_evidence_and_source_urls_make_relevant_gap_retrieval_eligible() -> None:
    evidence = [
        {
            "evidence_id": f"ev-{idx}",
            "source_url": f"https://source{idx}.example/case",
            "quote_or_evidence": (
                "Computer vision and drone imagery identify plantas daninhas using image analysis."
            ),
            "source_quality_score": 0.9,
            "evidence_confidence_score": 0.9,
            "confidence": "high",
        }
        for idx in range(3)
    ]

    summary = diagnose_gaps_quantitative(
        run_id="live-evidence-test",
        evidence_items=evidence,
        accepted_evidence_items=evidence,
        collection_metrics={
            "source_category_count": 2,
            "minimums": {"source_category_count": 2},
        },
        extraction_metrics={"total_extractions": 3, "failed_extractions": 0},
    )

    cv_gap = next(g for g in summary.gaps if g.gap_type == GapType.COMPUTER_VISION_GAP)
    assert cv_gap.production_allowed is True
    assert cv_gap.thresholds["observed_evidence_coverage"] == 1.0
    assert cv_gap.features.confidence.supporting_source_count > 0.0
    assert cv_gap.features.confidence.source_category_coverage == 1.0
    assert len(cv_gap.supporting_evidence_ids) == 3


def test_only_matching_evidence_ids_are_attached_to_a_gap() -> None:
    evidence = [
        {
            "evidence_id": "ev-cv",
            "source_url": "https://vision.example/case",
            "quote_or_evidence": "Visão computacional detecta plantas daninhas em imagens de drones.",
            "source_quality_score": 0.9,
            "evidence_confidence_score": 0.9,
            "confidence": "high",
        },
        {
            "evidence_id": "ev-company",
            "source_url": "https://company.example/about",
            "quote_or_evidence": "A empresa atende produtores rurais em todo o Brasil.",
            "source_quality_score": 0.8,
            "evidence_confidence_score": 0.8,
            "confidence": "high",
        },
        {
            "evidence_id": "ev-market",
            "source_url": "https://market.example/profile",
            "quote_or_evidence": "A plataforma oferece automação para operações agrícolas.",
            "source_quality_score": 0.8,
            "evidence_confidence_score": 0.8,
            "confidence": "high",
        },
    ]

    summary = diagnose_gaps_quantitative(
        run_id="matching-provenance-test",
        evidence_items=evidence,
        accepted_evidence_items=evidence,
    )

    cv_gap = next(g for g in summary.gaps if g.gap_type == GapType.COMPUTER_VISION_GAP)
    assert cv_gap.thresholds["observed_evidence_coverage"] == 0.3333
    assert cv_gap.production_allowed is True
    assert cv_gap.supporting_evidence_ids == ["ev-cv"]


def test_high_severity_detected_gap_requires_review_without_failing_diagnosis() -> None:
    evidence = [
        {
            "evidence_id": f"ev-{idx}",
            "source_url": f"https://vision{idx}.example/case",
            "quote_or_evidence": "Computer vision identifies weeds in drone imagery.",
            "source_quality_score": 0.5,
            "evidence_confidence_score": 0.2,
            "confidence": "low",
        }
        for idx in range(3)
    ]
    rejected = [
        {
            "evidence_id": f"rejected-{idx}",
            "source_url": f"https://rejected{idx}.example/case",
            "quote_or_evidence": "Rejected weak evidence.",
        }
        for idx in range(5)
    ]
    claims = [
        {
            "claim_id": f"claim-{idx}",
            "claim_text": "Unsupported non-critical claim",
            "support_status": "unsupported",
            "is_critical": False,
        }
        for idx in range(5)
    ]

    summary = diagnose_gaps_quantitative(
        run_id="detected-gap-status-test",
        evidence_items=evidence,
        accepted_evidence_items=evidence,
        rejected_evidence_items=rejected,
        claims=claims,
    )

    cv_gap = next(g for g in summary.gaps if g.gap_type == GapType.COMPUTER_VISION_GAP)
    assert cv_gap.severity_score > cv_gap.thresholds["production_threshold"]
    assert cv_gap.status == GapDiagnosisStatus.NEEDS_REVIEW
    assert cv_gap.production_allowed is True
    assert summary.gap_diagnosis_status != GapDiagnosisStatus.FAILED


def test_unrelated_gap_is_not_created_from_silence() -> None:
    evidence = [
        {
            "evidence_id": f"ev-{idx}",
            "source_url": f"https://source{idx}.example/case",
            "quote_or_evidence": "Computer vision detects weeds in drone imagery.",
            "source_quality_score": 0.9,
            "evidence_confidence_score": 0.9,
            "confidence": "high",
        }
        for idx in range(3)
    ]

    summary = diagnose_gaps_quantitative(
        run_id="no-false-gap-test",
        evidence_items=evidence,
        accepted_evidence_items=evidence,
    )

    cyber_gap = next(g for g in summary.gaps if g.gap_type == GapType.CYBERSECURITY_AI_GAP)
    assert cyber_gap.production_allowed is False
    assert cyber_gap.supporting_evidence_ids == []
