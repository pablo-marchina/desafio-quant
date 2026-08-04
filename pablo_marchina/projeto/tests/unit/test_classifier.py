"""Tests for src.classification.ai_native_classifier."""

from datetime import datetime, timezone

from pydantic import HttpUrl

from src.classification.ai_native_classifier import (
    ClassificationResult,
    classify_ai_native,
)
from src.extraction.schemas import (
    AINativeLevel,
    ConfidenceLevel,
    Evidence,
    SourceType,
    StartupProfile,
)


def _make_evidence(claim: str = "AI signal") -> Evidence:
    return Evidence(
        claim=claim,
        source_url=HttpUrl("https://example.com"),
        source_type=SourceType.OFFICIAL_SITE,
        quote_or_evidence="Extracted signal.",
        confidence=ConfidenceLevel.MEDIUM,
        collected_at=datetime.now(timezone.utc),  # noqa: UP017
    )


def _make_profile(
    ai_signals: list[str] | None = None,
    product_summary: str = "",
    description: str = "",
    tech_stack_signals: list[str] | None = None,
    confidence_score: float = 0.5,
    sources: list[Evidence] | None = None,
) -> StartupProfile:
    return StartupProfile(
        startup_name="Test Startup",
        website=HttpUrl("https://example.com"),
        sector="Technology",
        description=description or "A technology company.",
        product_summary=product_summary or "Building software solutions.",
        ai_signals=ai_signals or [],
        tech_stack_signals=tech_stack_signals or [],
        sources=sources or [],
        confidence_score=confidence_score,
    )


# ---------------------------------------------------------------------------
# NON_AI
# ---------------------------------------------------------------------------


def test_classify_non_ai() -> None:
    profile = _make_profile(ai_signals=[], confidence_score=0.6)
    result = classify_ai_native(profile)

    assert result.classification == AINativeLevel.NON_AI
    assert result.confidence in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM)
    assert "No AI signals" in result.reasoning
    assert result.missing_evidence


def test_classify_non_ai_low_confidence() -> None:
    profile = _make_profile(ai_signals=[], confidence_score=0.1)
    result = classify_ai_native(profile)

    assert result.classification == AINativeLevel.NON_AI
    assert result.confidence == ConfidenceLevel.LOW


# ---------------------------------------------------------------------------
# AI_ASSISTED
# ---------------------------------------------------------------------------


def test_classify_ai_assisted() -> None:
    profile = _make_profile(
        ai_signals=["AI signal: machine learning"],
        product_summary="We build accounting software for small businesses.",
        confidence_score=0.6,
    )
    result = classify_ai_native(profile)

    assert result.classification == AINativeLevel.AI_ASSISTED
    assert result.confidence == ConfidenceLevel.LOW
    assert "no evidence" in result.reasoning.lower()


def test_classify_ai_assisted_single_signal() -> None:
    profile = _make_profile(
        ai_signals=["AI signal: nlp"],
        product_summary="A task management tool.",
        confidence_score=0.7,
    )
    result = classify_ai_native(profile)

    assert result.classification == AINativeLevel.AI_ASSISTED
    assert result.confidence == ConfidenceLevel.LOW


# ---------------------------------------------------------------------------
# AI_ENABLED
# ---------------------------------------------------------------------------


def test_classify_ai_enabled() -> None:
    profile = _make_profile(
        ai_signals=[
            "AI signal: machine learning",
            "AI signal: natural language processing",
            "AI signal: predictive model",
        ],
        product_summary="Our platform includes AI features for data analysis.",
        confidence_score=0.6,
    )
    result = classify_ai_native(profile)

    assert result.classification == AINativeLevel.AI_ENABLED
    assert result.confidence in (ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW)
    assert "AI features" in result.reasoning or "core value" in result.reasoning


def test_classify_ai_enabled_low_signals() -> None:
    profile = _make_profile(
        ai_signals=["AI signal: machine learning"],
        product_summary="Our product has AI capabilities for reporting.",
        confidence_score=0.6,
    )
    result = classify_ai_native(profile)

    assert result.classification == AINativeLevel.AI_ENABLED


# ---------------------------------------------------------------------------
# AI_NATIVE
# ---------------------------------------------------------------------------


def test_classify_ai_native() -> None:
    profile = _make_profile(
        ai_signals=[
            "AI signal: machine learning",
            "AI signal: deep learning",
            "AI signal: computer vision",
            "AI signal: llm",
            "AI signal: neural network",
        ],
        product_summary=(
            "Our AI-powered platform uses deep learning and computer vision "
            "to deliver an ai-driven predictive model for quality inspection."
        ),
        tech_stack_signals=["Tech stack: pytorch", "Tech stack: python"],
        confidence_score=0.7,
        sources=[_make_evidence("AI signal")],
    )
    result = classify_ai_native(profile)

    assert result.classification == AINativeLevel.AI_NATIVE
    assert result.confidence in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM)
    assert "core value" in result.reasoning.lower() or "dependency" in result.reasoning.lower()
    assert result.evidence_used


def test_classify_ai_native_high_confidence() -> None:
    profile = _make_profile(
        ai_signals=[
            "AI signal: machine learning",
            "AI signal: deep learning",
            "AI signal: computer vision",
            "AI signal: llm",
            "AI signal: neural network",
            "AI signal: generative ai",
            "AI signal: nlp",
            "AI signal: predictive model",
        ],
        product_summary=(
            "Our AI-powered platform uses deep learning and computer vision "
            "to deliver an ai-driven predictive model for quality inspection."
        ),
        tech_stack_signals=["Tech stack: pytorch"],
        confidence_score=0.8,
    )
    result = classify_ai_native(profile)

    assert result.classification == AINativeLevel.AI_NATIVE
    assert result.confidence == ConfidenceLevel.HIGH


# ---------------------------------------------------------------------------
# AI_NATIVE_SERVICE
# ---------------------------------------------------------------------------


def test_classify_ai_native_service() -> None:
    profile = _make_profile(
        ai_signals=[
            "AI signal: machine learning",
            "AI signal: deep learning",
            "AI signal: nlp",
            "AI signal: llm",
            "AI signal: predictive model",
        ],
        product_summary=(
            "Our AI-powered platform uses deep learning and proprietary data "
            "with fine-tuned language models trained on exclusive legal content."
        ),
        description=(
            "We integrate with enterprise workflow systems to automate " "legal document review using custom AI models."
        ),
        tech_stack_signals=["Tech stack: pytorch", "Tech stack: langchain"],
        confidence_score=0.7,
        sources=[_make_evidence("AI signal")],
    )
    result = classify_ai_native(profile)

    assert result.classification == AINativeLevel.AI_NATIVE_SERVICE
    assert result.confidence == ConfidenceLevel.MEDIUM
    assert "proprietary" in result.reasoning.lower() or "service" in result.reasoning.lower()
    assert result.evidence_used


# ---------------------------------------------------------------------------
# Weak evidence
# ---------------------------------------------------------------------------


def test_classify_weak_evidence() -> None:
    profile = _make_profile(
        ai_signals=["AI signal: machine learning"],
        product_summary="A simple todo app.",
        confidence_score=0.15,
    )
    result = classify_ai_native(profile)

    assert result.classification in (
        AINativeLevel.AI_ASSISTED,
        AINativeLevel.NON_AI,
    )
    assert result.confidence == ConfidenceLevel.LOW
    assert result.missing_evidence


# ---------------------------------------------------------------------------
# Evidence propagation
# ---------------------------------------------------------------------------


def test_classify_evidence_used_includes_sources() -> None:
    sources = [
        _make_evidence("AI signal"),
        _make_evidence("Company description"),
        _make_evidence("Founder mentions"),
    ]
    profile = _make_profile(
        ai_signals=[
            "AI signal: machine learning",
            "AI signal: deep learning",
            "AI signal: nlp",
            "AI signal: llm",
            "AI signal: generative ai",
        ],
        product_summary="Our AI-powered platform uses deep learning.",
        confidence_score=0.7,
        sources=sources,
    )
    result = classify_ai_native(profile)

    assert len(result.evidence_used) >= 2
    for ev in result.evidence_used:
        assert isinstance(ev, Evidence)


# ---------------------------------------------------------------------------
# Result shape
# ---------------------------------------------------------------------------


def test_classify_result_shape() -> None:
    profile = _make_profile()
    result = classify_ai_native(profile)

    assert isinstance(result, ClassificationResult)
    assert result.startup_name == "Test Startup"
    assert isinstance(result.classification, AINativeLevel)
    assert isinstance(result.confidence, ConfidenceLevel)
    assert isinstance(result.reasoning, str)
    assert isinstance(result.evidence_used, list)
    assert isinstance(result.missing_evidence, list)
