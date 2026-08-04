"""Tests for src.validation.evidence_validator."""

from datetime import datetime, timezone

from pydantic import HttpUrl

from src.extraction.schemas import ConfidenceLevel, Evidence, SourceType
from src.validation.evidence_validator import (
    EvidenceKind,
    ValidatedEvidence,
    flag_unsourced_claims,
    validate_evidence,
    validate_evidence_batch,
)


def _make_evidence(
    claim: str = "Machine learning used in core product",
    url: str = "https://example.com",
    source_type: SourceType = SourceType.OFFICIAL_SITE,
    quote: str = "The company uses machine learning for core product features.",
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM,
) -> Evidence:
    return Evidence(
        claim=claim,
        source_url=HttpUrl(url),
        source_type=source_type,
        quote_or_evidence=quote,
        confidence=confidence,
        collected_at=datetime.now(timezone.utc),  # noqa: UP017
    )


# ---------------------------------------------------------------------------
# 1. Official source + explicit quote → FACT / HIGH
# ---------------------------------------------------------------------------


def test_official_explicit_fact_high() -> None:
    evidence = _make_evidence(
        claim="Machine learning used in core product",
        source_type=SourceType.OFFICIAL_SITE,
        quote="The company uses machine learning for core product features.",
    )
    result = validate_evidence(evidence)

    assert result.evidence_kind == EvidenceKind.FACT
    assert result.confidence == ConfidenceLevel.HIGH
    assert result.claim == "Machine learning used in core product"
    assert "machine learning" in result.quote_or_evidence


# ---------------------------------------------------------------------------
# 2. News source + explicit quote → FACT / MEDIUM
# ---------------------------------------------------------------------------


def test_news_explicit_fact_medium() -> None:
    evidence = _make_evidence(
        claim="AI-powered analytics platform funded",
        source_type=SourceType.NEWS,
        quote="Startup raised $10M for its AI-powered analytics platform.",
    )
    result = validate_evidence(evidence)

    assert result.evidence_kind == EvidenceKind.FACT
    assert result.confidence == ConfidenceLevel.MEDIUM
    assert result.source_type == SourceType.NEWS


# ---------------------------------------------------------------------------
# 3. Directory source + explicit quote → FACT / MEDIUM
# ---------------------------------------------------------------------------


def test_directory_explicit_fact_medium() -> None:
    evidence = _make_evidence(
        claim="NLP solutions for healthcare",
        source_type=SourceType.DIRECTORY,
        quote="Profiled company offers NLP solutions for healthcare.",
    )
    result = validate_evidence(evidence)

    assert result.evidence_kind == EvidenceKind.FACT
    assert result.confidence == ConfidenceLevel.MEDIUM


# ---------------------------------------------------------------------------
# 4. Short/vague quote (< 20 chars) → WEAK_INFERENCE / LOW
# ---------------------------------------------------------------------------


def test_short_quote_weak_inference_low() -> None:
    evidence = _make_evidence(
        quote="Uses AI.",
    )
    result = validate_evidence(evidence)

    assert result.evidence_kind == EvidenceKind.WEAK_INFERENCE
    assert result.confidence == ConfidenceLevel.LOW
    assert result.quote_or_evidence == "Uses AI."


# ---------------------------------------------------------------------------
# 5. Empty quote → UNVERIFIED / LOW
# ---------------------------------------------------------------------------


def test_empty_quote_unverified_low() -> None:
    evidence = _make_evidence(quote="")
    result = validate_evidence(evidence)

    assert result.evidence_kind == EvidenceKind.UNVERIFIED
    assert result.confidence == ConfidenceLevel.LOW
    assert result.quote_or_evidence == ""


# ---------------------------------------------------------------------------
# 6. Whitespace-only quote → UNVERIFIED / LOW
# ---------------------------------------------------------------------------


def test_whitespace_quote_unverified_low() -> None:
    evidence = _make_evidence(quote="   ")
    result = validate_evidence(evidence)

    assert result.evidence_kind == EvidenceKind.UNVERIFIED
    assert result.confidence == ConfidenceLevel.LOW


# ---------------------------------------------------------------------------
# 7. Hypothesis keywords in quote → HYPOTHESIS / MEDIUM
# ---------------------------------------------------------------------------


def test_hypothesis_language_in_quote() -> None:
    evidence = _make_evidence(
        claim="Computer vision expansion planned",
        quote="The company may expand into computer vision next year.",
    )
    result = validate_evidence(evidence)

    assert result.evidence_kind == EvidenceKind.HYPOTHESIS
    assert result.confidence == ConfidenceLevel.MEDIUM


# ---------------------------------------------------------------------------
# 8. Indirect quote (longer text but no claim-word overlap) → STRONG_INFERENCE
# ---------------------------------------------------------------------------


def test_indirect_quote_strong_inference_medium() -> None:
    evidence = _make_evidence(
        claim="Uses PyTorch framework",
        quote="The company builds software for data scientists.",
    )
    result = validate_evidence(evidence)

    assert result.evidence_kind == EvidenceKind.STRONG_INFERENCE
    assert result.confidence == ConfidenceLevel.MEDIUM


# ---------------------------------------------------------------------------
# 9. flag_unsourced_claims — claim without matching evidence
# ---------------------------------------------------------------------------


def test_flag_unsourced_claim() -> None:
    evidence = _make_evidence(claim="AI signals found", quote="Uses ML for predictions.")
    flagged = flag_unsourced_claims(
        claims=["Uses ML for predictions", "Raises the next round"],
        evidence_list=[evidence],
    )
    assert "Raises the next round" in flagged
    assert "Uses ML for predictions" not in flagged


# ---------------------------------------------------------------------------
# 10. flag_unsourced_claims — all claims match
# ---------------------------------------------------------------------------


def test_all_claims_sourced_empty() -> None:
    evidence = _make_evidence(claim="AI signals found", quote="Uses ML for predictions.")
    flagged = flag_unsourced_claims(
        claims=["AI signals found", "Uses ML for predictions"],
        evidence_list=[evidence],
    )
    assert flagged == []


# ---------------------------------------------------------------------------
# 11. Mixed batch validation
# ---------------------------------------------------------------------------


def test_mixed_batch_validation() -> None:
    ev1 = _make_evidence(
        claim="LLM for contract analysis",
        quote="Company uses LLM for contract analysis.",
        source_type=SourceType.OFFICIAL_SITE,
    )
    ev2 = _make_evidence(
        claim="AI platform Series A",
        quote="Startup raised Series A for AI platform.",
        source_type=SourceType.NEWS,
    )
    ev3 = _make_evidence(
        claim="Technology company",
        quote="Has AI.",
    )
    ev4 = _make_evidence(
        claim="Funding amount",
        quote="",
    )

    results = validate_evidence_batch([ev1, ev2, ev3, ev4])

    assert len(results) == 4
    assert results[0].evidence_kind == EvidenceKind.FACT
    assert results[0].confidence == ConfidenceLevel.HIGH
    assert results[1].evidence_kind == EvidenceKind.FACT
    assert results[1].confidence == ConfidenceLevel.MEDIUM
    assert results[2].evidence_kind == EvidenceKind.WEAK_INFERENCE
    assert results[2].confidence == ConfidenceLevel.LOW
    assert results[3].evidence_kind == EvidenceKind.UNVERIFIED
    assert results[3].confidence == ConfidenceLevel.LOW


# ---------------------------------------------------------------------------
# 12. ValidatedEvidence shape
# ---------------------------------------------------------------------------


def test_validated_evidence_shape() -> None:
    evidence = _make_evidence()
    result = validate_evidence(evidence)

    assert isinstance(result, ValidatedEvidence)
    assert isinstance(result.claim, str)
    assert isinstance(result.evidence_kind, EvidenceKind)
    assert isinstance(result.confidence, ConfidenceLevel)
    assert isinstance(result.source_type, SourceType)
    assert isinstance(result.collected_at, datetime)


# ---------------------------------------------------------------------------
# 13. Claim without quote → UNVERIFIED / LOW (sem trecho)
# ---------------------------------------------------------------------------


def test_claim_without_quote_unverified() -> None:
    evidence = _make_evidence(quote="")
    result = validate_evidence(evidence)

    assert result.evidence_kind == EvidenceKind.UNVERIFIED
    assert result.confidence == ConfidenceLevel.LOW


# ---------------------------------------------------------------------------
# 14. Blog source + explicit quote → FACT / MEDIUM
# ---------------------------------------------------------------------------


def test_blog_explicit_fact_medium() -> None:
    evidence = _make_evidence(
        claim="PyTorch in production pipeline",
        source_type=SourceType.BLOG,
        quote="We integrated PyTorch into our production pipeline.",
    )
    result = validate_evidence(evidence)

    assert result.evidence_kind == EvidenceKind.FACT
    assert result.confidence == ConfidenceLevel.MEDIUM
