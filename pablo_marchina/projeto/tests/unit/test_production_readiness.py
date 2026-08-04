"""Tests for Production AI Readiness scoring."""

from __future__ import annotations

import pytest

from src.classification.ai_native_classifier import ClassificationResult
from src.extraction.schemas import AINativeLevel, ConfidenceLevel, StartupProfile
from src.scoring.production_readiness import (
    ProductionReadinessResult,
    ReadinessDimension,
    compute_production_readiness,
)
from src.validation.evidence_validator import ValidatedEvidence


def _make_profile(
    sector: str = "HealthTech",
    customers: list[str] | None = None,
    funding: list[str] | None = None,
    tech_stack: list[str] | None = None,
    ai_signals: list[str] | None = None,
    description: str = "AI-powered healthcare platform deployed in production",
    product_summary: str = "Real-time inference for medical imaging",
) -> StartupProfile:
    return StartupProfile(
        startup_name="TestAI",
        website="https://testai.com",
        sector=sector,
        description=description,
        product_summary=product_summary,
        customers=customers or [],
        funding_signals=funding or [],
        tech_stack_signals=tech_stack or [],
        ai_signals=ai_signals or [],
        confidence_score=0.8,
    )


def _make_result(level: AINativeLevel = AINativeLevel.AI_NATIVE) -> ClassificationResult:
    return ClassificationResult(
        startup_name="TestAI",
        classification=level,
        confidence=ConfidenceLevel.HIGH,
        reasoning="test",
        evidence_used=[],
        missing_evidence=[],
    )


def _make_evidence(
    claim: str,
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
) -> ValidatedEvidence:
    return ValidatedEvidence(
        source_url="https://example.com",
        source_type="news",
        quote_or_evidence="test evidence",
        evidence_kind="fact",
        claim=claim,
        confidence=confidence,
        collected_at="2025-01-01",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def high_readiness_profile() -> StartupProfile:
    return _make_profile(
        sector="HealthTech",
        customers=["SUS", "Hospital Albert Einstein", "Dasa"],
        funding=["Series A $5M", "Seed $1M"],
        tech_stack=["PyTorch", "Kubernetes", "Docker", "Kafka", "PostgreSQL"],
        ai_signals=["low latency", "real-time inference", "data pipeline", "compliance"],
        description=("Production-deployed AI for healthcare with real-time inference and data pipelines"),
        product_summary="Real-time inference for medical imaging with controlled deployment",
    )


@pytest.fixture
def low_readiness_profile() -> StartupProfile:
    return _make_profile(
        sector="E-commerce",
        customers=[],
        funding=[],
        tech_stack=["Python"],
        ai_signals=[],
        description="Early stage startup exploring AI concepts",
        product_summary="Exploring AI ideas",
    )


@pytest.fixture
def high_confidence_evidence() -> list[ValidatedEvidence]:
    return [
        _make_evidence("Funded startup with 5 customers", ConfidenceLevel.HIGH),
        _make_evidence("Deployed in production environment", ConfidenceLevel.HIGH),
        _make_evidence("Uses NVIDIA GPU inference", ConfidenceLevel.HIGH),
    ]


@pytest.fixture
def low_confidence_evidence() -> list[ValidatedEvidence]:
    return [
        _make_evidence("Mentioned AI briefly", ConfidenceLevel.LOW),
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestComputeProductionReadiness:
    def test_high_readiness(self, high_readiness_profile, high_confidence_evidence):
        result = compute_production_readiness(
            high_readiness_profile,
            _make_result(AINativeLevel.AI_NATIVE),
            high_confidence_evidence,
        )
        assert isinstance(result, ProductionReadinessResult)
        assert result.production_readiness_score >= 50
        assert len(result.score_breakdown) == 4
        for _, dim in result.score_breakdown.items():
            assert isinstance(dim, ReadinessDimension)
            assert 0 <= dim.raw_score <= 100
            assert 0 <= dim.adjusted_score <= 100
        assert result.confidence in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM)

    def test_low_readiness(self, low_readiness_profile, low_confidence_evidence):
        result = compute_production_readiness(
            low_readiness_profile,
            _make_result(AINativeLevel.AI_ASSISTED),
            low_confidence_evidence,
        )
        assert result.production_readiness_score <= 30
        assert result.confidence == ConfidenceLevel.LOW

    def test_no_evidence(self):
        profile = _make_profile()
        result = compute_production_readiness(
            profile,
            _make_result(AINativeLevel.AI_ENABLED),
            [],
        )
        assert result.production_readiness_score <= 40
        assert result.missing_evidence

    def test_dimension_names(self, high_readiness_profile, high_confidence_evidence):
        result = compute_production_readiness(
            high_readiness_profile,
            _make_result(AINativeLevel.AI_NATIVE_SERVICE),
            high_confidence_evidence,
        )
        expected = {
            "real_users_and_deployment",
            "scale_and_inference",
            "privacy_and_governance",
            "data_infrastructure",
        }
        assert set(result.score_breakdown.keys()) == expected

    def test_each_dimension_boundaries(self):
        profile = _make_profile(
            sector="HealthTech",
            customers=["a", "b", "c", "d"],
            funding=["Series A"],
            tech_stack=["PyTorch", "Kubernetes", "Docker", "Kafka", "Spark", "PostgreSQL"],
            ai_signals=[
                "low latency",
                "real-time inference",
                "data pipeline",
                "etl",
                "compliance",
                "privacy",
            ],
            description="Production AI with full data infrastructure",
            product_summary="High-throughput real-time inference platform with data pipelines",
        )
        evidence = [
            _make_evidence("Large customer base", ConfidenceLevel.HIGH),
            _make_evidence("Substantial funding round", ConfidenceLevel.HIGH),
            _make_evidence("Production deployment with GPU inference", ConfidenceLevel.HIGH),
        ]
        result = compute_production_readiness(profile, _make_result(AINativeLevel.AI_NATIVE), evidence)
        for name, dim in result.score_breakdown.items():
            assert dim.raw_score >= 0, f"{name} raw_score negative"
            assert dim.raw_score <= 100, f"{name} raw_score > 100"
            assert dim.adjusted_score >= 0, f"{name} adjusted_score negative"
            assert dim.adjusted_score <= 100, f"{name} adjusted_score > 100"
            assert dim.dimension_name == name
            assert dim.weight > 0

    def test_weighted_sum_calculation(self, high_readiness_profile, high_confidence_evidence):
        result = compute_production_readiness(
            high_readiness_profile,
            _make_result(AINativeLevel.AI_NATIVE),
            high_confidence_evidence,
        )
        expected = sum(dim.adjusted_score * dim.weight for dim in result.score_breakdown.values())
        assert abs(result.production_readiness_score - expected) < 0.2
