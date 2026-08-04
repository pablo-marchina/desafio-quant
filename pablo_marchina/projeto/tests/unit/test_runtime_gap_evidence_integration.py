from __future__ import annotations

from datetime import UTC, datetime

from src.agents.extractor_agent import _build_evidence_item
from src.diagnosis.gap_diagnosis_scoring import diagnose_gaps_quantitative
from src.diagnosis.schemas import GapType
from src.extraction.schemas import ConfidenceLevel, Evidence, SourceType, StartupProfile
from src.orchestration.node_impl import _runtime_decision_inventory


def _profile(source: Evidence) -> StartupProfile:
    return StartupProfile(
        startup_name="Pix Force Release Smoke",
        website="https://pixforce.com/",
        country="Brazil",
        sector="Computer Vision",
        description="Industrial computer-vision company.",
        product_summary="AI systems for visual inspection.",
        ai_signals=["computer vision", "artificial intelligence"],
        sources=[source],
        confidence_score=0.9,
    )


def _vision_item(evidence_id: str, text: str, url: str) -> dict:
    source = Evidence(
        claim=text,
        source_url=url,
        source_type=SourceType.OFFICIAL_SITE,
        quote_or_evidence=text,
        confidence=ConfidenceLevel.HIGH,
        collected_at=datetime.now(UTC),
    )
    return _build_evidence_item(
        {
            "id": evidence_id,
            "text": text,
            "source_url": url,
            "source_id": evidence_id,
            "source_type": "official_site",
            "collected_at": datetime.now(UTC).isoformat(),
        },
        _profile(source),
        SourceType.OFFICIAL_SITE,
    )


def test_normalized_official_evidence_promotes_computer_vision_gap() -> None:
    evidence = [
        _vision_item(
            "pix-home",
            "Pix Force develops artificial-intelligence and computer-vision solutions for industrial operations.",
            "https://pixforce.com/",
        ),
        _vision_item(
            "pix-about",
            "A página oficial descreve visão computacional e inspeção visual para interpretar imagens e vídeos.",
            "https://pixforce.com/pt-br/quem-somos/",
        ),
        {
            "evidence_id": "irrelevant-funding",
            "text": "the company announced a funding round",
            "source_id": "news",
            "source_url": "https://example.com/funding",
            "source_type": "news",
            "confidence": "medium",
            "source_quality_score": 0.6,
            "extraction_confidence": 0.6,
        },
    ]

    summary = diagnose_gaps_quantitative(
        run_id="runtime-gap-integration",
        startup_id="pix-force",
        startup_profile={
            "startup_name": "Pix Force Release Smoke",
            "sector": "Computer Vision",
            "description": "Industrial computer vision company",
        },
        evidence_items=evidence,
        accepted_evidence_items=evidence,
        rejected_evidence_items=[],
        claims=[],
        evidence_validation={"accepted_evidence_count": len(evidence)},
        ai_native_score=0.9,
        nvidia_fit_score=0.8,
        scoring_metrics={},
        collection_metrics={
            "source_categories_covered": ["official_site", "news"],
            "expected_categories": 2,
        },
        extraction_metrics={"total_extractions": 3, "failed_extractions": 0},
        inventory=_runtime_decision_inventory(),
    )

    vision = next(gap for gap in summary.gaps if gap.gap_type is GapType.COMPUTER_VISION_GAP)
    assert vision.production_allowed is True
    assert vision.status.value in {"passed", "failed"}
    assert set(vision.supporting_evidence_ids) == {"pix-home", "pix-about"}
    assert "irrelevant-funding" not in vision.supporting_evidence_ids
