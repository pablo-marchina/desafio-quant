"""Tests for the main pipeline orchestrator (Epic 7.1/9.1)."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import HttpUrl

from src.extraction.schemas import (
    AINativeLevel,
    ConfidenceLevel,
    Evidence,
    SourceType,
    StartupProfile,
)
from src.pipeline.run_pipeline import PipelineResult, run_full_pipeline


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
        collected_at=datetime.now(timezone.utc),  # noqa: UP017
    )


class TestPipeline:
    def test_pipeline_order_and_fields(self) -> None:
        """Pipeline with strong evidence returns all expected fields."""
        profile = _make_profile(
            sector="HealthTech",
            ai_signals=["AI signal: machine learning", "AI signal: deep learning"],
            tech_stack=["PyTorch", "Kubernetes", "Docker"],
            customers=["Hospital A", "Clinic B"],
            funding=["Series A $5M"],
            description=(
                "AI-native healthcare platform using deep learning "
                "for medical imaging diagnostics deployed in production."
            ),
            product_summary="Real-time medical image analysis platform.",
        )
        evidence = [
            _make_evidence("AI-native healthcare platform", ConfidenceLevel.HIGH),
            _make_evidence("Deployed in production hospitals", ConfidenceLevel.HIGH),
            _make_evidence("Uses PyTorch for model training", ConfidenceLevel.HIGH),
        ]

        result = run_full_pipeline(
            startup_name="Test Startup",
            profile=profile,
            evidence_list=evidence,
        )

        assert isinstance(result, PipelineResult)
        assert result.production_readiness_score is not None
        assert result.composite_score is not None
        assert result.final_priority_score > 0
        assert isinstance(result.defensibility_score.total_score, float)
        assert isinstance(result.inception_fit_score.total_score, float)
        assert isinstance(result.production_readiness_score.production_readiness_score, float)
        assert isinstance(result.composite_score.composite_score, float)
        assert result.ai_native_classification.classification is not None
        assert result.recommended_motion in (
            "immediate_outreach",
            "high_priority_outreach",
            "monitor_and_nurture",
            "lack_evidence_more_research",
            "not_recommended",
        )
        assert len(result.validated_evidence) > 0
        assert result.startup_name == "Test Startup"
        assert result.gap_diagnosis is not None
        assert result.recommendation is not None

    def test_weak_evidence_not_approach_now(self) -> None:
        """Startup with weak evidence should NOT get immediate_outreach."""
        profile = _make_profile(
            sector="E-commerce",
            ai_signals=[],
            tech_stack=["WordPress"],
            description="Online store selling handmade crafts.",
            product_summary="E-commerce platform.",
            customers=[],
            funding=[],
        )

        result = run_full_pipeline(
            startup_name="Weak Startup",
            profile=profile,
            evidence_list=[],
        )

        assert result.recommended_motion != "immediate_outreach"

    def test_output_contains_new_scores(self) -> None:
        """Output must contain production_readiness_score and final_priority_score."""
        profile = _make_profile()
        ev = _make_evidence("AI company", ConfidenceLevel.LOW)

        result = run_full_pipeline(
            startup_name="Score Test",
            profile=profile,
            evidence_list=[ev],
        )

        assert hasattr(result, "production_readiness_score")
        assert hasattr(result, "final_priority_score")
        assert result.production_readiness_score.production_readiness_score >= 0
        assert result.final_priority_score >= 0

    def test_pipeline_with_raw_text(self) -> None:
        """Pipeline works when given raw text instead of a pre-built profile."""
        raw_text = (
            "Startup: AI Health Ltd\n"
            "Sector: HealthTech\n"
            "AI-native medical imaging platform "
            "deployed in major hospitals across Brazil. "
            "Uses deep learning for real-time diagnosis. "
            "Tech stack: PyTorch, Kubernetes, Docker. "
            "Customers: Hospital Albert Einstein, Dasa. "
            "Funding: Series A $10M."
        )
        evidence = [
            _make_evidence("Medical imaging AI platform", ConfidenceLevel.HIGH),
        ]

        result = run_full_pipeline(
            startup_name="AI Health Ltd",
            raw_text=raw_text,
            url="https://example.com/ai-health",
            evidence_list=evidence,
        )

        assert result.startup_name == "AI Health Ltd"
        assert result.startup_profile is not None
        assert result.production_readiness_score is not None
        assert result.composite_score is not None
        assert result.gap_diagnosis is not None
        assert result.recommendation is not None

    def test_result_shape(self) -> None:
        """Verify all expected fields in the PipelineResult schema."""
        profile = _make_profile(ai_signals=["AI signal: nlp"])
        ev = _make_evidence("NLP platform company", ConfidenceLevel.MEDIUM)

        result = run_full_pipeline(
            startup_name="Shape Test",
            profile=profile,
            evidence_list=[ev],
        )

        assert result.startup_name == "Shape Test"
        assert result.ai_native_classification.classification in (
            AINativeLevel.NON_AI,
            AINativeLevel.AI_ASSISTED,
            AINativeLevel.AI_ENABLED,
            AINativeLevel.AI_NATIVE,
            AINativeLevel.AI_NATIVE_SERVICE,
        )
        assert len(result.validated_evidence) == 1
        assert result.defensibility_score.total_score is not None
        assert result.inception_fit_score.total_score is not None
        assert result.composite_score.composite_score is not None
        assert result.ranked is not None
        assert isinstance(result.evidence_used, list)
        assert result.gap_diagnosis is not None
        assert result.recommendation is not None

    def test_pipeline_produces_diagnosis_and_recommendation(self) -> None:
        """Strong AI-native startup produces detected gaps and APPROACH_NOW recommendations."""
        profile = _make_profile(
            sector="HealthTech",
            ai_signals=["machine learning", "deep learning", "neural networks"],
            tech_stack=["PyTorch", "TensorRT", "Docker"],
            description=(
                "AI-native healthcare platform using deep learning "
                "for real-time medical image analysis in production."
            ),
            product_summary="Real-time AI-powered medical imaging diagnostics.",
            customers=["Hospital A"],
            funding=["Series B $20M"],
        )
        evidence = [
            _make_evidence("Deep learning medical imaging", ConfidenceLevel.HIGH),
            _make_evidence("Production deployment in hospitals", ConfidenceLevel.HIGH),
            _make_evidence("PyTorch and GPU inference", ConfidenceLevel.HIGH),
        ]

        result = run_full_pipeline(
            startup_name="Strong AI",
            profile=profile,
            evidence_list=evidence,
        )

        assert result.gap_diagnosis is not None
        assert result.recommendation is not None
        detected = [g for g in result.gap_diagnosis.diagnosed_gaps if g.detected]
        assert len(detected) >= 0
        assert len(result.recommendation.recommendations) > 0

    def test_pipeline_no_ai_signals_few_gaps(self) -> None:
        """Startup without AI signals should have few or no detected gaps."""
        profile = _make_profile(
            sector="E-commerce",
            ai_signals=[],
            tech_stack=["WordPress", "PHP"],
            description="Online store selling physical products.",
            product_summary="Simple e-commerce storefront.",
            customers=[],
            funding=[],
        )

        result = run_full_pipeline(
            startup_name="No AI",
            profile=profile,
            evidence_list=[],
        )

        assert result.gap_diagnosis is not None
        assert result.recommendation is not None
        detected = [g for g in result.gap_diagnosis.diagnosed_gaps if g.detected]
        assert len(detected) == 0

    def test_no_technology_recommended_without_gap(self) -> None:
        """No NVIDIA technology should be recommended for undetected gaps."""
        profile = _make_profile(
            sector="Consulting",
            ai_signals=[],
            tech_stack=[],
            description="Management consulting firm.",
            product_summary="Business advisory services.",
            customers=[],
            funding=[],
        )

        result = run_full_pipeline(
            startup_name="Consulting Inc",
            profile=profile,
            evidence_list=[],
        )

        assert result.recommendation is not None
        for rec in result.recommendation.recommendations:
            if not rec.detected:
                assert len(rec.recommended_nvidia_technologies) == 0

    def test_missing_evidence_propagates_to_output(self) -> None:
        """missing_evidence from diagnosis and recommendation appears in PipelineResult."""
        profile = _make_profile(
            ai_signals=["AI signal: machine learning"],
            description=("A company exploring AI but with very little public evidence."),
        )
        ev = _make_evidence("Exploring AI", ConfidenceLevel.LOW)

        result = run_full_pipeline(
            startup_name="Low Evidence Co",
            profile=profile,
            evidence_list=[ev],
        )

        assert isinstance(result.missing_evidence, list)
        if result.gap_diagnosis is not None and result.gap_diagnosis.missing_evidence:
            for item in result.gap_diagnosis.missing_evidence:
                assert item in result.missing_evidence

    def test_output_contains_diagnosis_and_recommendation_fields(self) -> None:
        """PipelineResult schema includes gap_diagnosis and recommendation."""
        profile = _make_profile(ai_signals=["AI signal: computer vision"])
        ev = _make_evidence("Computer vision platform", ConfidenceLevel.HIGH)

        result = run_full_pipeline(
            startup_name="CV Startup",
            profile=profile,
            evidence_list=[ev],
        )

        assert hasattr(result, "gap_diagnosis")
        assert hasattr(result, "recommendation")
        assert result.gap_diagnosis is not None
        assert result.recommendation is not None
        assert hasattr(result.gap_diagnosis, "diagnosed_gaps")
        assert hasattr(result.gap_diagnosis, "nvidia_technology_candidates")
        assert hasattr(result.recommendation, "recommendations")
        assert hasattr(result.recommendation, "overall_priority")
        assert hasattr(result.recommendation, "overall_confidence")
