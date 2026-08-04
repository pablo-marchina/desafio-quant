"""Source trust and freshness ranking for evidence-first RAG product spikes."""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from src.rag.schemas import RetrievedContext


class SourceQualityRankingConfig(BaseModel):
    enabled: bool = True
    official_nvidia_domains: tuple[str, ...] = (
        "docs.nvidia.com",
        "developer.nvidia.com",
        "nvidia.com",
    )
    relevance_weight: float = 0.25
    trust_weight: float = 0.40
    freshness_weight: float = 0.25
    lifecycle_weight: float = 0.10


class SourceQualityFeatures(BaseModel):
    provenance_score: float = Field(ge=0.0, le=1.0)
    trust_score: float = Field(ge=0.0, le=1.0)
    freshness_score: float = Field(ge=0.0, le=1.0)
    lifecycle_score: float = Field(ge=0.0, le=1.0)
    relevance_score: float = Field(ge=0.0, le=1.0)
    combined_score: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)


class RankedSourceContext(BaseModel):
    context: RetrievedContext
    rank: int
    features: SourceQualityFeatures


def rank_contexts_by_source_quality(
    contexts: list[RetrievedContext],
    config: SourceQualityRankingConfig | None = None,
    *,
    now: datetime | None = None,
) -> list[RankedSourceContext]:
    """Rank contexts by trust, freshness, lifecycle, and relevance without external calls."""

    resolved = config or SourceQualityRankingConfig()
    if not resolved.enabled:
        return [
            RankedSourceContext(
                context=context,
                rank=index + 1,
                features=score_source_quality(context, resolved, now=now),
            )
            for index, context in enumerate(contexts)
        ]

    scored = [
        RankedSourceContext(
            context=context,
            rank=0,
            features=score_source_quality(context, resolved, now=now),
        )
        for context in contexts
    ]
    scored.sort(
        key=lambda item: (
            item.features.combined_score,
            item.features.trust_score,
            item.features.freshness_score,
            item.context.relevance_score,
        ),
        reverse=True,
    )
    return [
        RankedSourceContext(context=item.context, rank=index + 1, features=item.features)
        for index, item in enumerate(scored)
    ]


def score_source_quality(
    context: RetrievedContext,
    config: SourceQualityRankingConfig | None = None,
    *,
    now: datetime | None = None,
) -> SourceQualityFeatures:
    resolved = config or SourceQualityRankingConfig()
    reasons: list[str] = []
    provenance_score = _provenance_score(context, reasons)
    trust_score = _trust_score(context, resolved, reasons)
    freshness_score = _freshness_score(context, now=now, reasons=reasons)
    lifecycle_score = _lifecycle_score(context, reasons)
    relevance_score = max(0.0, min(1.0, context.relevance_score))
    combined = (
        relevance_score * resolved.relevance_weight
        + trust_score * resolved.trust_weight
        + freshness_score * resolved.freshness_weight
        + lifecycle_score * resolved.lifecycle_weight
    )
    return SourceQualityFeatures(
        provenance_score=round(provenance_score, 4),
        trust_score=round(trust_score, 4),
        freshness_score=round(freshness_score, 4),
        lifecycle_score=round(lifecycle_score, 4),
        relevance_score=round(relevance_score, 4),
        combined_score=round(max(0.0, min(1.0, combined)), 4),
        reasons=reasons,
    )


def _provenance_score(context: RetrievedContext, reasons: list[str]) -> float:
    if context.source_id and context.url:
        reasons.append("has_source_id_and_url")
        return 1.0
    if context.source_id or context.url:
        reasons.append("partial_provenance")
        return 0.55
    reasons.append("missing_provenance")
    return 0.20


def _trust_score(context: RetrievedContext, config: SourceQualityRankingConfig, reasons: list[str]) -> float:
    if not context.url:
        reasons.append("missing_url_trust_penalty")
        return 0.25
    host = urlparse(context.url).netloc.casefold()
    if host.startswith("www."):
        host = host[4:]
    if any(host == domain or host.endswith(f".{domain}") for domain in config.official_nvidia_domains):
        reasons.append("official_nvidia_source")
        return 1.0
    if "nvidia" in host:
        reasons.append("nvidia_related_source")
        return 0.75
    if host.endswith(".edu") or host.endswith(".gov"):
        reasons.append("institutional_source")
        return 0.70
    reasons.append("non_official_source")
    return 0.45


def _freshness_score(context: RetrievedContext, *, now: datetime | None, reasons: list[str]) -> float:
    current_time = (now or datetime.now(UTC)).astimezone(UTC)
    if context.valid_until:
        valid_until = _parse_datetime(context.valid_until)
        if valid_until is not None:
            days_remaining = (valid_until - current_time).days
            if days_remaining < 0:
                reasons.append("expired_source")
                return 0.0
            if days_remaining <= 30:
                reasons.append("expires_soon")
                return 0.65
            reasons.append("fresh_valid_until")
            return 1.0
    if context.deprecated_at or context.superseded_by:
        reasons.append("deprecated_or_superseded_source")
        return 0.15
    reasons.append("freshness_metadata_missing")
    return 0.60


def _lifecycle_score(context: RetrievedContext, reasons: list[str]) -> float:
    if not context.is_active:
        reasons.append("inactive_source")
        return 0.0
    if context.deprecated_at or context.superseded_by:
        reasons.append("deprecated_lifecycle")
        return 0.2
    reasons.append("active_lifecycle")
    return 1.0


def _parse_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
