from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.extraction.schemas import ConfidenceLevel, Evidence, SourceType, StartupProfile


def make_evidence() -> Evidence:
    return Evidence(
        claim="Startup states it offers AI copilots.",
        source_url="https://example.com/blog/ai-copilots",
        source_type=SourceType.BLOG,
        quote_or_evidence="We launched AI copilots for operations teams.",
        confidence=ConfidenceLevel.MEDIUM,
        collected_at=datetime.now(UTC),
    )


def test_startup_profile_creation() -> None:
    profile = StartupProfile(
        startup_name="Example AI",
        website="https://example.com",
        sector="SaaS",
        description="Fictional example for tests.",
        product_summary="An operations platform with AI workflows.",
        ai_signals=["Mentions AI copilots"],
        sources=[make_evidence()],
        confidence_score=0.8,
    )
    assert profile.country == "Brazil"
    assert profile.sources[0].source_type == SourceType.BLOG


def test_evidence_creation() -> None:
    evidence = make_evidence()
    assert evidence.confidence == ConfidenceLevel.MEDIUM


def test_enum_validation() -> None:
    evidence = Evidence(
        claim="Example claim",
        source_url="https://example.com",
        source_type="official_site",
        quote_or_evidence="Example evidence",
        confidence="high",
        collected_at=datetime.now(UTC),
    )
    assert evidence.source_type == SourceType.OFFICIAL_SITE


def test_invalid_confidence_rejected() -> None:
    with pytest.raises(ValidationError):
        Evidence(
            claim="Example claim",
            source_url="https://example.com",
            source_type="official_site",
            quote_or_evidence="Example evidence",
            confidence="certain",
            collected_at=datetime.now(UTC),
        )


def test_confidence_level_from_score() -> None:
    assert ConfidenceLevel.from_score(0.9) == ConfidenceLevel.HIGH
    assert ConfidenceLevel.from_score(0.7) == ConfidenceLevel.HIGH
    assert ConfidenceLevel.from_score(0.6) == ConfidenceLevel.MEDIUM
    assert ConfidenceLevel.from_score(0.4) == ConfidenceLevel.MEDIUM
    assert ConfidenceLevel.from_score(0.3) == ConfidenceLevel.LOW
    assert ConfidenceLevel.from_score(0.0) == ConfidenceLevel.LOW
