"""Tests for src.scoring.defensibility_score."""

from datetime import datetime, timezone

from pydantic import HttpUrl

from src.classification.ai_native_classifier import ClassificationResult
from src.extraction.schemas import AINativeLevel, ConfidenceLevel, SourceType, StartupProfile
from src.scoring.defensibility_score import (
    DefensibilityScoreResult,
    DimensionScore,
    compute_defensibility_score,
)
from src.validation.evidence_validator import EvidenceKind, ValidatedEvidence


def _make_validated_evidence(
    claim: str = "AI signals found",
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM,
    evidence_kind: EvidenceKind = EvidenceKind.FACT,
    quote: str = "The company uses machine learning for core features.",
) -> ValidatedEvidence:
    return ValidatedEvidence(
        claim=claim,
        source_url=HttpUrl("https://example.com"),
        source_type=SourceType.OFFICIAL_SITE,
        quote_or_evidence=quote,
        confidence=confidence,
        evidence_kind=evidence_kind,
        collected_at=datetime.now(timezone.utc),  # noqa: UP017
    )


def _make_profile(
    ai_signals: list[str] | None = None,
    product_summary: str = "",
    description: str = "",
    tech_stack_signals: list[str] | None = None,
    customers: list[str] | None = None,
    funding_signals: list[str] | None = None,
    confidence_score: float = 0.5,
    sector: str = "Technology",
) -> StartupProfile:
    return StartupProfile(
        startup_name="Test Startup",
        website=HttpUrl("https://example.com"),
        sector=sector,
        description=description or "A technology company.",
        product_summary=product_summary or "Building software solutions.",
        ai_signals=ai_signals or [],
        tech_stack_signals=tech_stack_signals or [],
        customers=customers or [],
        funding_signals=funding_signals or [],
        sources=[],
        confidence_score=confidence_score,
    )


def _make_classification(
    level: AINativeLevel = AINativeLevel.AI_ENABLED,
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM,
) -> ClassificationResult:
    return ClassificationResult(
        startup_name="Test Startup",
        classification=level,
        confidence=confidence,
        reasoning=f"Classified as {level.value}.",
    )


# ---------------------------------------------------------------------------
# Scenario 1: Wrapper frágil — AI-enabled, few signals, external API dependency
# ---------------------------------------------------------------------------


def test_wrapper_fragil() -> None:
    profile = _make_profile(
        ai_signals=[
            "AI signal: machine learning",
            "AI signal: llm",
        ],
        product_summary="Our platform integrates GPT to generate reports.",
        description="A reporting tool with AI features powered by OpenAI.",
        tech_stack_signals=["Tech stack: python"],
        customers=[],
        funding_signals=[],
        confidence_score=0.5,
    )
    classification = _make_classification(AINativeLevel.AI_ENABLED, ConfidenceLevel.LOW)
    evidence = [
        _make_validated_evidence("AI signals found", ConfidenceLevel.MEDIUM),
        _make_validated_evidence("Company description", ConfidenceLevel.LOW),
        _make_validated_evidence("Tech stack signals", ConfidenceLevel.LOW),
    ]

    result = compute_defensibility_score(profile, classification, evidence)

    assert isinstance(result, DefensibilityScoreResult)
    assert result.total_score >= 0
    assert result.total_score <= 100
    assert result.total_score < 50, f"Wrapper should score low, got {result.total_score}"
    assert len(result.score_breakdown) == 6
    assert result.missing_evidence


# ---------------------------------------------------------------------------
# Scenario 2: AI-enabled com evidência média — some signals, some customers
# ---------------------------------------------------------------------------


def test_ai_enabled_evidencia_media() -> None:
    profile = _make_profile(
        ai_signals=[
            "AI signal: machine learning",
            "AI signal: nlp",
            "AI signal: predictive model",
        ],
        product_summary="Our platform includes AI features for customer analytics.",
        description="A data analytics company serving enterprise customers.",
        tech_stack_signals=["Tech stack: python", "Tech stack: aws"],
        customers=["ACME Corp", "Globex Inc"],
        funding_signals=["Series A: $5M"],
        confidence_score=0.6,
    )
    classification = _make_classification(AINativeLevel.AI_ENABLED, ConfidenceLevel.MEDIUM)
    evidence = [
        _make_validated_evidence("AI signals found", ConfidenceLevel.MEDIUM),
        _make_validated_evidence("Company description", ConfidenceLevel.MEDIUM),
        _make_validated_evidence("Customer mentions", ConfidenceLevel.MEDIUM),
        _make_validated_evidence("Funding signals", ConfidenceLevel.MEDIUM),
        _make_validated_evidence("Tech stack signals", ConfidenceLevel.MEDIUM),
    ]

    result = compute_defensibility_score(profile, classification, evidence)

    assert isinstance(result, DefensibilityScoreResult)
    assert 10 <= result.total_score <= 50, f"Expected medium score, got {result.total_score}"
    assert result.confidence in (ConfidenceLevel.MEDIUM, ConfidenceLevel.HIGH)


# ---------------------------------------------------------------------------
# Scenario 3: AI-native com sinais fortes
# ---------------------------------------------------------------------------


def test_ai_native_sinais_fortes() -> None:
    profile = _make_profile(
        ai_signals=[
            "AI signal: machine learning",
            "AI signal: deep learning",
            "AI signal: llm",
            "AI signal: computer vision",
            "AI signal: neural network",
            "AI signal: nlp",
            "AI signal: generative ai",
            "AI signal: predictive model",
        ],
        product_summary=(
            "Our AI-powered platform uses deep learning and computer vision "
            "to deliver predictive models for quality inspection."
        ),
        description=(
            "An AI-native company with proprietary data and workflow integration "
            "deployed in production at enterprise customers."
        ),
        tech_stack_signals=[
            "Tech stack: pytorch",
            "Tech stack: tensorflow",
            "Tech stack: kubernetes",
        ],
        customers=["ACME Corp", "Globex Inc", "Initech"],
        funding_signals=["Series B: $20M"],
        confidence_score=0.8,
        sector="HealthTech",
    )
    classification = _make_classification(AINativeLevel.AI_NATIVE, ConfidenceLevel.HIGH)
    evidence = [
        _make_validated_evidence("AI signals found", ConfidenceLevel.HIGH),
        _make_validated_evidence("Company description", ConfidenceLevel.HIGH),
        _make_validated_evidence("Customer mentions", ConfidenceLevel.HIGH),
        _make_validated_evidence("Funding signals", ConfidenceLevel.HIGH),
        _make_validated_evidence("Tech stack signals", ConfidenceLevel.HIGH),
    ]

    result = compute_defensibility_score(profile, classification, evidence)

    assert isinstance(result, DefensibilityScoreResult)
    assert result.total_score >= 50, f"Strong startup should score high, got {result.total_score}"
    assert result.confidence == ConfidenceLevel.HIGH
    assert "ai_core_dependency" in result.score_breakdown
    assert "replication_complexity" in result.score_breakdown


# ---------------------------------------------------------------------------
# Scenario 4: Tese forte mas evidência fraca
# ---------------------------------------------------------------------------


def test_tese_forte_evidencia_fraca() -> None:
    profile = _make_profile(
        ai_signals=[
            "AI signal: machine learning",
            "AI signal: deep learning",
            "AI signal: llm",
            "AI signal: computer vision",
            "AI signal: neural network",
            "AI signal: nlp",
            "AI signal: generative ai",
            "AI signal: predictive model",
        ],
        product_summary=(
            "Our AI-powered platform uses deep learning and computer vision " "to deliver predictive models."
        ),
        description="An AI-native company building computer vision solutions.",
        tech_stack_signals=["Tech stack: pytorch"],
        customers=[],
        funding_signals=[],
        confidence_score=0.8,
        sector="HealthTech",
    )
    classification = _make_classification(AINativeLevel.AI_NATIVE, ConfidenceLevel.HIGH)
    evidence = [
        _make_validated_evidence("AI signals found", ConfidenceLevel.LOW),
        _make_validated_evidence("Company description", ConfidenceLevel.LOW),
        _make_validated_evidence("Tech stack signals", ConfidenceLevel.LOW),
    ]

    result = compute_defensibility_score(profile, classification, evidence)

    assert isinstance(result, DefensibilityScoreResult)
    assert result.total_score >= 0
    assert result.total_score <= 100
    assert result.missing_evidence, "Expected missing evidence for weak evidence scenario"
    assert result.confidence == ConfidenceLevel.LOW, f"Expected LOW confidence, got {result.confidence.value}"


# ---------------------------------------------------------------------------
# Scenario 5: Sem evidência suficiente
# ---------------------------------------------------------------------------


def test_sem_evidencia_suficiente() -> None:
    profile = _make_profile(
        ai_signals=[],
        product_summary="A task management application.",
        description="A simple productivity tool.",
        tech_stack_signals=[],
        customers=[],
        funding_signals=[],
        confidence_score=0.15,
        sector="Technology",
    )
    classification = _make_classification(AINativeLevel.NON_AI, ConfidenceLevel.LOW)
    evidence: list[ValidatedEvidence] = []

    result = compute_defensibility_score(profile, classification, evidence)

    assert isinstance(result, DefensibilityScoreResult)
    assert result.total_score <= 20, f"No-evidence startup should score very low, got {result.total_score}"
    assert len(result.missing_evidence) >= 3
    assert result.confidence == ConfidenceLevel.LOW


# ---------------------------------------------------------------------------
# Result shape
# ---------------------------------------------------------------------------


def test_result_shape() -> None:
    profile = _make_profile()
    classification = _make_classification()
    evidence = [_make_validated_evidence()]

    result = compute_defensibility_score(profile, classification, evidence)

    assert isinstance(result, DefensibilityScoreResult)
    assert isinstance(result.total_score, float)
    assert isinstance(result.score_breakdown, dict)
    assert isinstance(result.confidence, ConfidenceLevel)
    assert isinstance(result.reasoning, str)
    assert isinstance(result.evidence_used, list)
    assert isinstance(result.missing_evidence, list)

    for _name, ds in result.score_breakdown.items():
        assert isinstance(ds, DimensionScore)
        assert 0 <= ds.raw_score <= 100
        assert 0 <= ds.adjusted_score <= 100
        assert 0 <= ds.weight <= 1
        assert isinstance(ds.confidence, ConfidenceLevel)
