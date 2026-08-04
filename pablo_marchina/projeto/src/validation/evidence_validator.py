"""Deterministic evidence validation — separates fact, inference, hypothesis, and unverified."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, HttpUrl

from src.extraction.schemas import ConfidenceLevel, Evidence, SourceType

_MIN_EXPLICIT_LENGTH = 20
_HYPOTHESIS_KEYWORDS: list[str] = [
    "may",
    "might",
    "could",
    "possibly",
    "perhaps",
    "suggests",
    "indicates",
    "likely",
    "unlikely",
    "potentially",
    "talvez",
    "pode ser",
    "possivelmente",
    "sugere",
    "indica",
]


class EvidenceKind(Enum):
    FACT = "fact"
    STRONG_INFERENCE = "strong_inference"
    WEAK_INFERENCE = "weak_inference"
    HYPOTHESIS = "hypothesis"
    UNVERIFIED = "unverified"


class ValidatedEvidence(BaseModel):
    claim: str
    source_url: HttpUrl
    source_type: SourceType
    quote_or_evidence: str
    confidence: ConfidenceLevel
    evidence_kind: EvidenceKind
    collected_at: datetime
    is_critical: bool = False


def _is_hypothesis(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in _HYPOTHESIS_KEYWORDS)


def _is_explicit_quote(quote: str, claim: str) -> bool:
    stripped = quote.strip()
    if len(stripped) < _MIN_EXPLICIT_LENGTH:
        return False
    claim_words = {w for w in claim.lower().split() if len(w) > 3}
    if not claim_words:
        return True
    quote_lower = stripped.lower()
    return any(w in quote_lower for w in claim_words)


def validate_evidence(evidence: Evidence) -> ValidatedEvidence:
    """Classify a single Evidence object into a ValidatedEvidence
    with deterministic evidence_kind and recalibrated confidence.

    Rules
    -----
    - Official source + explicit quote           → fact / high
    - Non-official trusted source + explicit quote → fact / medium
    - Hypothesis language in quote                → hypothesis / medium
    - Indirect quote (exists but not explicit)    → strong_inference / medium
    - Short or vague quote (< 20 chars)           → weak_inference / low
    - Empty or whitespace-only quote              → unverified / low
    """
    quote = evidence.quote_or_evidence
    claim = evidence.claim

    is_critical = evidence.source_type == SourceType.OFFICIAL_SITE

    if not quote or not quote.strip():
        return ValidatedEvidence(
            claim=claim,
            source_url=evidence.source_url,
            source_type=evidence.source_type,
            quote_or_evidence=quote,
            confidence=ConfidenceLevel.LOW,
            evidence_kind=EvidenceKind.UNVERIFIED,
            collected_at=evidence.collected_at,
            is_critical=is_critical,
        )

    stripped = quote.strip()

    if _is_hypothesis(stripped):
        return ValidatedEvidence(
            claim=claim,
            source_url=evidence.source_url,
            source_type=evidence.source_type,
            quote_or_evidence=quote,
            confidence=ConfidenceLevel.MEDIUM,
            evidence_kind=EvidenceKind.HYPOTHESIS,
            collected_at=evidence.collected_at,
            is_critical=is_critical,
        )

    if _is_explicit_quote(stripped, claim):
        if evidence.source_type == SourceType.OFFICIAL_SITE:
            confidence = ConfidenceLevel.HIGH
        else:
            confidence = ConfidenceLevel.MEDIUM

        return ValidatedEvidence(
            claim=claim,
            source_url=evidence.source_url,
            source_type=evidence.source_type,
            quote_or_evidence=quote,
            confidence=confidence,
            evidence_kind=EvidenceKind.FACT,
            collected_at=evidence.collected_at,
            is_critical=is_critical,
        )

    if len(stripped) >= _MIN_EXPLICIT_LENGTH:
        return ValidatedEvidence(
            claim=claim,
            source_url=evidence.source_url,
            source_type=evidence.source_type,
            quote_or_evidence=quote,
            confidence=ConfidenceLevel.MEDIUM,
            evidence_kind=EvidenceKind.STRONG_INFERENCE,
            collected_at=evidence.collected_at,
            is_critical=is_critical,
        )

    return ValidatedEvidence(
        claim=claim,
        source_url=evidence.source_url,
        source_type=evidence.source_type,
        quote_or_evidence=quote,
        confidence=ConfidenceLevel.LOW,
        evidence_kind=EvidenceKind.WEAK_INFERENCE,
        collected_at=evidence.collected_at,
        is_critical=is_critical,
    )


def validate_evidence_batch(evidence_list: list[Evidence]) -> list[ValidatedEvidence]:
    """Validate a batch of Evidence objects."""
    return [validate_evidence(ev) for ev in evidence_list]


def flag_unsourced_claims(
    claims: list[str],
    evidence_list: list[Evidence],
) -> list[str]:
    """Return claims that have no matching evidence.

    A claim matches if its text appears (case-insensitive) in
    any evidence's ``claim`` or ``quote_or_evidence`` fields.
    """
    unmatched: list[str] = []
    combined = " ".join(f"{ev.claim} {ev.quote_or_evidence}".lower() for ev in evidence_list)
    for claim in claims:
        if claim.lower() not in combined:
            unmatched.append(claim)
    return unmatched
