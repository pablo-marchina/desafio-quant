from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from src.sourcing.adapters.base import EvidenceSpan

logger = logging.getLogger(__name__)

_CLAIM_COOLDOWN = timedelta(hours=24)  # ignore exact duplicate claims within this window


@dataclass
class ValidatedClaim:
    """A claim that has been cross-validated across sources."""

    claim_text: str
    supporting_sources: list[EvidenceSpan] = field(default_factory=list)
    contradicting_sources: list[EvidenceSpan] = field(default_factory=list)
    aggregated_confidence: float = 0.0
    source_count: int = 0


@dataclass
class Contradiction:
    """A pair of contradictory claims from different sources."""

    claim_a: str
    claim_b: str
    source_a: str
    source_b: str
    severity: str = "medium"  # "low", "medium", "high"


@dataclass
class CrossValidationReport:
    """Full cross-validation report for a collection run."""

    total_claims: int = 0
    validated_claims: list[ValidatedClaim] = field(default_factory=list)
    contradictions: list[Contradiction] = field(default_factory=list)
    high_confidence_claims: int = 0
    low_confidence_claims: int = 0


# ── Normalisation helpers ─────────────────────────────────────────────────


def _normalise(text: str) -> str:
    """Lowercase, strip whitespace, collapse spaces."""
    import re

    return re.sub(r"\s+", " ", text.strip().lower())


def _is_similar_claim(a: str, b: str, threshold: float = 0.85) -> bool:
    """Check if two claim strings are similar enough to be the same claim."""
    try:
        from rapidfuzz import fuzz

        return fuzz.token_sort_ratio(_normalise(a), _normalise(b)) >= threshold * 100
    except ImportError:
        return _normalise(a) == _normalise(b)


# ── Negative/numeric claim extraction ──────────────────────────────────────


def _normalise_number(text: str) -> str | None:
    """Try to normalise a number mention (R$10M → 10000000, etc.)."""
    import re

    text = text.strip()
    # Match patterns like R$ 10M, $5M, R$ 1.5B, etc.
    m = re.match(r"^R?\$?\s*([\d,.]+)\s*([MBKmbk])?$", text)
    if m:
        return text
    # Match plain numbers with commas/dots
    m = re.match(r"^[\d,.]+$", text.replace(".", "").replace(",", ""))
    if m:
        return text
    return None


# ── Evidence Manager ──────────────────────────────────────────────────────


class EvidenceManager:
    """Cross-validate claims across multiple sources.

    Usage::

        mgr = EvidenceManager()
        for source_result in collected_sources:
            for span in source_result.evidence_spans:
                mgr.add_claim(span.text, span.source_url, span.confidence)
        report = mgr.cross_validate()
    """

    def __init__(self):
        self._claims: dict[str, list[EvidenceSpan]] = defaultdict(list)
        self._contradiction_pairs: list[tuple[str, str, EvidenceSpan, EvidenceSpan]] = []
        self._last_seen: dict[str, datetime] = {}

    def add_claim(self, claim_text: str, source_url: str, confidence: float = 0.5) -> None:
        """Register a new claim from a source.

        Args:
            claim_text: The extracted claim text.
            source_url: URL of the source that supports this claim.
            confidence: Confidence in the extraction (0.0–1.0).
        """
        span = EvidenceSpan(text=claim_text, source_url=source_url, confidence=confidence)
        key = _normalise(claim_text)

        # Dedup cooldown
        now = datetime.now(UTC)
        if key in self._last_seen and now - self._last_seen[key] < _CLAIM_COOLDOWN:
            return
        self._last_seen[key] = now

        # Group similar claims
        added = False
        for existing_key in list(self._claims.keys()):
            if _is_similar_claim(existing_key, key):
                self._claims[existing_key].append(span)
                added = True
                break

        if not added:
            self._claims[key].append(span)

    def cross_validate(self) -> CrossValidationReport:
        """Cross-validate all registered claims and produce a report.

        Returns:
            CrossValidationReport with validated claims and contradictions.
        """
        validated: list[ValidatedClaim] = []
        contradictions: list[Contradiction] = []

        for raw_claim, spans in self._claims.items():
            source_count = len(spans)
            avg_confidence = sum(s.confidence for s in spans) / source_count if source_count else 0.0

            # Boost confidence with multiple independent sources
            independence_factor = min(1.0 + source_count * 0.15, 1.5)
            final_confidence = min(avg_confidence * independence_factor, 1.0)

            validated.append(
                ValidatedClaim(
                    claim_text=raw_claim,
                    supporting_sources=spans,
                    aggregated_confidence=round(final_confidence, 3),
                    source_count=source_count,
                )
            )

        # ── Contradiction detection ──
        # Group claims that look numerically contradictory
        seen_claims = list(self._claims.keys())
        for i in range(len(seen_claims)):
            for j in range(i + 1, len(seen_claims)):
                ci = seen_claims[i]
                cj = seen_claims[j]
                if self._is_contradictory(ci, cj):
                    contradictions.append(
                        Contradiction(
                            claim_a=ci[:100],
                            claim_b=cj[:100],
                            source_a=self._claims[ci][0].source_url,
                            source_b=self._claims[cj][0].source_url,
                            severity="high" if _normalise_number(ci) and _normalise_number(cj) else "medium",
                        )
                    )

        high_conf = sum(1 for v in validated if v.aggregated_confidence >= 0.7)
        low_conf = sum(1 for v in validated if v.aggregated_confidence < 0.4)

        return CrossValidationReport(
            total_claims=len(validated),
            validated_claims=validated,
            contradictions=contradictions,
            high_confidence_claims=high_conf,
            low_confidence_claims=low_conf,
        )

    @staticmethod
    def _is_contradictory(a: str, b: str) -> bool:
        """Heuristic: detect if two claims are contradictory (e.g., different funding values)."""
        na = _normalise_number(a)
        nb = _normalise_number(b)
        if na and nb and na != nb:
            return True
        return False
