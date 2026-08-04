"""Tests for Startup Action Brief (Epic 10)."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import HttpUrl

from src.briefing.action_brief import build_action_brief
from src.briefing.markdown_renderer import render_action_brief_markdown
from src.briefing.schemas import BriefVerdict, StartupActionBrief
from src.extraction.schemas import (
    ConfidenceLevel,
    Evidence,
    SourceType,
    StartupProfile,
)
from src.pipeline.run_pipeline import run_full_pipeline


def _make_profile(
    sector: str = "Technology",
    ai_signals: list[str] | None = None,
    tech_stack: list[str] | None = None,
    description: str = "A technology company using AI for core features.",
    product_summary: str = "AI-powered analytics platform.",
    customers: list[str] | None = None,
    funding: list[str] | None = None,
) -> StartupProfile:
    return StartupProfile(
        startup_name="Test Startup",
        website=HttpUrl("https://example.com"),
        sector=sector,
        description=description,
        product_summary=product_summary,
        ai_signals=ai_signals or [],
        tech_stack_signals=tech_stack or [],
        customers=customers or [],
        funding_signals=funding or [],
        sources=[],
        confidence_score=0.6,
    )


def _make_evidence(
    claim: str,
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
) -> Evidence:
    return Evidence(
        claim=claim,
        source_url=HttpUrl("https://example.com"),
        source_type=SourceType.OFFICIAL_SITE,
        quote_or_evidence="The company uses AI for core features.",
        confidence=confidence,
        collected_at=datetime.now(UTC),
    )


class TestActionBrief:
    def test_high_fit_startup(self) -> None:
        """High-confidence AI-native startup produces non-negative verdict."""
        profile = _make_profile(
            sector="HealthTech",
            ai_signals=["AI signal: machine learning", "deep learning", "neural networks"],
            tech_stack=["PyTorch", "TensorRT", "Docker", "Kubernetes"],
            description=(
                "AI-native healthcare platform using deep learning "
                "for real-time medical image analysis in production."
            ),
            product_summary="Real-time AI-powered medical imaging diagnostics.",
            customers=["Hospital A", "Clinic B"],
            funding=["Series B $20M"],
        )
        evidence = [
            _make_evidence("Deep learning medical imaging", ConfidenceLevel.HIGH),
            _make_evidence("Production deployment in hospitals", ConfidenceLevel.HIGH),
            _make_evidence("PyTorch and GPU inference", ConfidenceLevel.HIGH),
        ]

        result = run_full_pipeline("HighFit Startup", profile=profile, evidence_list=evidence)
        brief = build_action_brief(result)

        assert isinstance(brief, StartupActionBrief)
        assert brief.startup_name == "HighFit Startup"
        assert brief.verdict != BriefVerdict.NOT_RECOMMENDED
        assert brief.final_priority_score > 0
        assert len(brief.evidence_used) > 0
        assert len(brief.sections) >= 5

    def test_weak_evidence_brief(self) -> None:
        """Weak evidence produces verdict that respects pipeline motion."""
        profile = _make_profile(
            sector="E-commerce",
            ai_signals=[],
            tech_stack=["WordPress"],
            description="Online store selling handmade crafts.",
            product_summary="E-commerce platform.",
            customers=[],
            funding=[],
        )

        result = run_full_pipeline("Weak Evidence Co", profile=profile, evidence_list=[])
        brief = build_action_brief(result)

        assert brief.recommended_motion != "immediate_outreach"
        assert brief.verdict in (
            BriefVerdict.NEEDS_VALIDATION,
            BriefVerdict.NOT_RECOMMENDED,
            BriefVerdict.EARLY_STAGE,
        )

    def test_no_gaps_clear(self) -> None:
        """Startup with no AI signals has no detected gaps."""
        profile = _make_profile(
            sector="Consulting",
            ai_signals=[],
            tech_stack=[],
            description="Management consulting firm.",
            product_summary="Business advisory services.",
            customers=[],
            funding=[],
        )

        result = run_full_pipeline("NoGap Co", profile=profile, evidence_list=[])
        build_action_brief(result)

        diag = result.gap_diagnosis
        detected = [g for g in (diag.diagnosed_gaps if diag else []) if g.detected]
        assert len(detected) == 0

    def test_missing_evidence_included(self) -> None:
        """missing_evidence from pipeline propagates to brief."""
        profile = _make_profile(
            ai_signals=["AI signal: machine learning"],
            description="A company exploring AI but with very little public evidence.",
        )
        ev = _make_evidence("Exploring AI", ConfidenceLevel.LOW)

        result = run_full_pipeline("Low Evidence Co", profile=profile, evidence_list=[ev])
        brief = build_action_brief(result)

        if result.missing_evidence:
            for item in result.missing_evidence:
                assert item in brief.missing_evidence

    def test_no_tech_without_gap(self) -> None:
        """No NVIDIA technology recommended without a diagnosed gap."""
        profile = _make_profile(
            sector="Consulting",
            ai_signals=[],
            tech_stack=[],
            description="Management consulting firm.",
            product_summary="Business advisory services.",
            customers=[],
            funding=[],
        )

        result = run_full_pipeline("No Tech Co", profile=profile, evidence_list=[])
        brief = build_action_brief(result)

        for rec in brief.recommendations:
            if not rec.get("detected", True):
                assert len(rec.get("recommended_nvidia_technologies", [])) == 0

    def test_uncertainties_section(self) -> None:
        """Brief includes uncertainties when gaps are inferred."""
        profile = _make_profile(
            sector="HealthTech",
            ai_signals=["AI signal: computer vision"],
            tech_stack=["PyTorch"],
            description="Healthcare AI company with limited public evidence.",
            product_summary="AI medical imaging.",
            customers=[],
            funding=[],
        )
        ev = _make_evidence("Medical imaging AI", ConfidenceLevel.MEDIUM)

        result = run_full_pipeline("Uncertain Co", profile=profile, evidence_list=[ev])
        brief = build_action_brief(result)

        if brief.uncertainties:
            for u in brief.uncertainties:
                assert u.description
                assert u.source
                assert u.impact
        assert isinstance(brief.uncertainties, list)

    def test_markdown_render(self) -> None:
        """Markdown output contains basic structure and all brief sections."""
        profile = _make_profile(
            sector="HealthTech",
            ai_signals=["AI signal: machine learning", "deep learning"],
            tech_stack=["PyTorch", "Docker"],
            description="AI healthcare platform.",
            product_summary="AI diagnostics.",
            customers=["Hospital A"],
            funding=["Seed $1M"],
        )
        ev = _make_evidence("AI healthcare platform", ConfidenceLevel.HIGH)

        result = run_full_pipeline("Markdown Test", profile=profile, evidence_list=[ev])
        brief = build_action_brief(result)
        md = render_action_brief_markdown(brief)

        assert isinstance(md, str)
        assert len(md) > 100
        assert "# Startup Action Brief: Markdown Test" in md
        assert "## Executive Summary" in md
        assert "## Why This Startup Matters" in md
        assert "## AI-Native Maturity" in md
        assert "## Scores Overview" in md
        assert "## Evidence" in md
        assert "## Next Action" in md
        assert len(brief.sections) >= 5

    def test_brief_schema_validation(self) -> None:
        """StartupActionBrief validates required fields."""
        profile = _make_profile(ai_signals=["AI signal: nlp"])
        ev = _make_evidence("NLP platform", ConfidenceLevel.MEDIUM)

        result = run_full_pipeline("Schema Test", profile=profile, evidence_list=[ev])
        brief = build_action_brief(result)

        assert brief.startup_name == "Schema Test"
        assert brief.website
        assert brief.sector
        assert brief.one_line_summary
        assert isinstance(brief.final_priority_score, float)
        assert isinstance(brief.missing_evidence, list)
        assert isinstance(brief.uncertainties, list)
        assert isinstance(brief.sections, list)
        assert len(brief.sections) >= 3

    def test_json_serialization(self) -> None:
        """Brief is JSON-serializable."""
        profile = _make_profile(ai_signals=["AI signal: computer vision"])
        ev = _make_evidence("CV platform", ConfidenceLevel.HIGH)

        result = run_full_pipeline("JSON Test", profile=profile, evidence_list=[ev])
        brief = build_action_brief(result)

        json_data = brief.model_dump_json(indent=2)
        assert isinstance(json_data, str)
        assert '"startup_name"' in json_data
        assert '"verdict"' in json_data
        assert '"sections"' in json_data

    def test_weak_evidence_not_high_priority(self) -> None:
        """Low confidence means verdict is not HIGH_PRIORITY."""
        profile = _make_profile(
            sector="E-commerce",
            ai_signals=[],
            tech_stack=["WordPress"],
            description="Simple online store.",
            product_summary="E-commerce platform.",
            customers=[],
            funding=[],
        )

        result = run_full_pipeline("Low Conf", profile=profile, evidence_list=[])
        brief = build_action_brief(result)

        assert brief.verdict != BriefVerdict.HIGH_PRIORITY
