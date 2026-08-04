"""Tests for src.scoring.inception_fit_score."""

from datetime import datetime, timezone

from pydantic import HttpUrl

from src.classification.ai_native_classifier import ClassificationResult
from src.extraction.schemas import (
    AINativeLevel,
    ConfidenceLevel,
    SourceType,
    StartupProfile,
    TechnicalGap,
)
from src.scoring.inception_fit_score import (
    InceptionFitDimension,
    InceptionFitScoreResult,
    compute_inception_fit_score,
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
# Scenario 1: Alto fit NVIDIA + evidência forte
# ---------------------------------------------------------------------------


def test_alto_fit_nvidia_evidencia_forte() -> None:
    profile = _make_profile(
        ai_signals=[
            "AI signal: machine learning",
            "AI signal: deep learning",
            "AI signal: llm",
            "AI signal: computer vision",
            "AI signal: neural network",
            "AI signal: generative ai",
            "AI signal: gpt",
        ],
        product_summary=("Our AI platform uses deep learning and computer vision " "for real-time quality inspection."),
        description=(
            "An AI-native company with computer vision and LLM inference "
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

    result = compute_inception_fit_score(profile, classification, 75.0, evidence)

    assert isinstance(result, InceptionFitScoreResult)
    assert result.total_score >= 70, f"Expected high score, got {result.total_score}"
    assert result.confidence == ConfidenceLevel.HIGH
    assert result.recommended_motion_hint == "approach_now"
    assert len(result.detected_gaps) >= 2
    assert result.score_breakdown


# ---------------------------------------------------------------------------
# Scenario 2: AI-native promissora mas evidência fraca
# ---------------------------------------------------------------------------


def test_ai_native_promissora_evidencia_fraca() -> None:
    profile = _make_profile(
        ai_signals=[
            "AI signal: machine learning",
            "AI signal: deep learning",
            "AI signal: llm",
            "AI signal: computer vision",
            "AI signal: neural network",
            "AI signal: generative ai",
            "AI signal: agent",
        ],
        product_summary=("Our AI platform uses deep learning and LLMs for document analysis."),
        description=(
            "An AI-native company building document intelligence with " "computer vision and language models."
        ),
        tech_stack_signals=["Tech stack: pytorch"],
        customers=["ACME Corp"],
        funding_signals=[],
        confidence_score=0.7,
        sector="LegalTech",
    )
    classification = _make_classification(AINativeLevel.AI_NATIVE, ConfidenceLevel.MEDIUM)
    evidence = [
        _make_validated_evidence("AI signals found", ConfidenceLevel.LOW),
        _make_validated_evidence("Company description", ConfidenceLevel.MEDIUM),
        _make_validated_evidence("Customer mentions", ConfidenceLevel.MEDIUM),
        _make_validated_evidence("Tech stack signals", ConfidenceLevel.LOW),
    ]

    result = compute_inception_fit_score(profile, classification, 60.0, evidence)

    assert isinstance(result, InceptionFitScoreResult)
    assert result.total_score >= 25
    assert result.total_score <= 80
    assert result.recommended_motion_hint in ("validate_manually", "monitor")
    assert result.confidence in (ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW)
    assert result.total_score < 60


# ---------------------------------------------------------------------------
# Scenario 3: Sem fit claro com NVIDIA
# ---------------------------------------------------------------------------


def test_sem_fit_claro_com_nvidia() -> None:
    profile = _make_profile(
        ai_signals=[],
        product_summary="A simple task management application.",
        description="A productivity tool for small teams.",
        tech_stack_signals=[],
        customers=[],
        funding_signals=[],
        confidence_score=0.15,
        sector="Technology",
    )
    classification = _make_classification(AINativeLevel.NON_AI, ConfidenceLevel.LOW)
    evidence: list[ValidatedEvidence] = []

    result = compute_inception_fit_score(profile, classification, 5.0, evidence)

    assert isinstance(result, InceptionFitScoreResult)
    assert result.total_score < 40, f"Expected low score, got {result.total_score}"
    assert result.recommended_motion_hint == "discard_for_now"
    assert len(result.detected_gaps) == 0
    assert result.missing_evidence


# ---------------------------------------------------------------------------
# Scenario 4: Muito inicial para Inception
# ---------------------------------------------------------------------------


def test_muito_inicial_para_inception() -> None:
    profile = _make_profile(
        ai_signals=["AI signal: machine learning"],
        product_summary="An early-stage AI analytics prototype.",
        description=("A startup building AI analytics with a small team and no paying customers."),
        tech_stack_signals=["Tech stack: python"],
        customers=["Beta user"],
        funding_signals=[],
        confidence_score=0.3,
        sector="Technology",
    )
    classification = _make_classification(AINativeLevel.AI_ASSISTED, ConfidenceLevel.LOW)
    evidence = [
        _make_validated_evidence("AI signals found", ConfidenceLevel.LOW),
        _make_validated_evidence("Company description", ConfidenceLevel.LOW),
        _make_validated_evidence("Customer mentions", ConfidenceLevel.LOW),
        _make_validated_evidence("Tech stack signals", ConfidenceLevel.LOW),
    ]

    result = compute_inception_fit_score(profile, classification, 20.0, evidence)

    assert isinstance(result, InceptionFitScoreResult)
    assert result.total_score >= 0
    assert result.total_score <= 100
    assert result.recommended_motion_hint in ("monitor", "discard_for_now")
    assert result.missing_evidence


# ---------------------------------------------------------------------------
# Scenario 5: Fit setorial forte, mas baixa maturidade
# ---------------------------------------------------------------------------


def test_fit_setorial_forte_mas_baixa_maturidade() -> None:
    profile = _make_profile(
        ai_signals=[],
        product_summary="Healthcare records management system.",
        description=("A platform for managing patient health records with basic reporting features."),
        tech_stack_signals=["Tech stack: python", "Tech stack: aws"],
        customers=["Local hospital"],
        funding_signals=["Seed: $500K"],
        confidence_score=0.4,
        sector="HealthTech",
    )
    classification = _make_classification(AINativeLevel.NON_AI, ConfidenceLevel.MEDIUM)
    evidence = [
        _make_validated_evidence("Company description", ConfidenceLevel.MEDIUM),
        _make_validated_evidence("Customer mentions", ConfidenceLevel.MEDIUM),
        _make_validated_evidence("Funding signals", ConfidenceLevel.MEDIUM),
        _make_validated_evidence("Tech stack signals", ConfidenceLevel.MEDIUM),
    ]

    result = compute_inception_fit_score(profile, classification, 15.0, evidence)

    assert isinstance(result, InceptionFitScoreResult)
    assert result.total_score >= 0
    assert result.total_score <= 70, f"Expected moderate-low score, got {result.total_score}"
    assert result.recommended_motion_hint in ("validate_manually", "monitor")
    assert result.score_breakdown
    assert TechnicalGap.HEALTHCARE_COMPLIANCE_NEED in result.detected_gaps


# ---------------------------------------------------------------------------
# Result shape
# ---------------------------------------------------------------------------


def test_result_shape() -> None:
    profile = _make_profile()
    classification = _make_classification()
    evidence = [_make_validated_evidence()]

    result = compute_inception_fit_score(profile, classification, 30.0, evidence)

    assert isinstance(result, InceptionFitScoreResult)
    assert isinstance(result.total_score, float)
    assert isinstance(result.score_breakdown, dict)
    assert isinstance(result.confidence, ConfidenceLevel)
    assert isinstance(result.detected_gaps, list)
    assert isinstance(result.recommended_motion_hint, str)
    assert isinstance(result.reasoning, str)
    assert isinstance(result.evidence_used, list)
    assert isinstance(result.missing_evidence, list)

    for _name, ds in result.score_breakdown.items():
        assert isinstance(ds, InceptionFitDimension)
        assert 0 <= ds.raw_score <= 100
        assert 0 <= ds.adjusted_score <= 100
        assert 0 <= ds.weight <= 1
        assert isinstance(ds.confidence, ConfidenceLevel)
