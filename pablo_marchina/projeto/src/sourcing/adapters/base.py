from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256


@dataclass(frozen=True)
class EvidenceSpan:
    """A span of text extracted from a source URL with confidence."""

    text: str
    source_url: str
    confidence: float = 0.5


@dataclass(frozen=True)
class SourceResult:
    """Result of collecting a single source URL."""

    target: str
    status: str
    raw_text: str
    evidence_spans: list[EvidenceSpan] = field(default_factory=list)
    content_hash: str = ""
    collected_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    error: str | None = None
    claims: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    confidence_score: float = 0.5


class SourceAdapter:
    """Abstract base for source-specific collection adapters.

    Subclasses override :meth:`collect` to fetch and extract data from a
    particular type of source (official website, careers page, etc.).
    """

    source_type = "generic"

    def collect(
        self,
        target: str,
    ) -> SourceResult:
        """Collect data from *target* (URL or identifier).

        Args:
            target: URL or identifier for the source to collect.

        Returns:
            SourceResult with extracted text, evidence spans, and status.
        """
        raise NotImplementedError


def build_source_result(
    target: str,
    raw_text: str,
    *,
    status: str = "collected",
    max_evidence_length: int = 500,
) -> SourceResult:
    """Quick-build a SourceResult from raw text with one evidence span."""
    digest = sha256(raw_text.encode("utf-8")).hexdigest()
    spans = (
        [EvidenceSpan(text=raw_text[:max_evidence_length], source_url=target, confidence=0.5)]
        if raw_text
        else []
    )
    return SourceResult(
        target=target,
        status=status,
        raw_text=raw_text,
        evidence_spans=spans,
        content_hash=digest,
    )
