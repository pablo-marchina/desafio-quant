from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from src.sourcing.source_registry import SourceCategory, SourceRecord


class SourceQualityInput(BaseModel):
    source_id: str
    url: str
    category: SourceCategory
    collected_at: datetime | None = None
    is_official: bool = False
    is_independent: bool = False
    robots_allowed: bool = True
    terms_allowed: bool = True
    duplicate_count: int = 0
    marketing_language_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    claim_support_ratio: float = Field(default=0.0, ge=0.0, le=1.0)


class SourceQualityScore(BaseModel):
    authority_score: float = Field(ge=0.0, le=1.0)
    freshness_score: float = Field(ge=0.0, le=1.0)
    proximity_score: float = Field(ge=0.0, le=1.0)
    independence_score: float = Field(ge=0.0, le=1.0)
    officialness_score: float = Field(ge=0.0, le=1.0)
    terms_compliance_score: float = Field(ge=0.0, le=1.0)
    robots_compliance_score: float = Field(ge=0.0, le=1.0)
    duplication_penalty: float = Field(ge=0.0, le=1.0)
    marketing_bias_penalty: float = Field(ge=0.0, le=1.0)
    claim_support_score: float = Field(ge=0.0, le=1.0)
    combined_score: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)


def score_public_source(
    source: SourceQualityInput,
    *,
    registry_record: SourceRecord | None = None,
    now: datetime | None = None,
) -> SourceQualityScore:
    current_time = now or datetime.now(UTC)
    authority = registry_record.authority_weight if registry_record else _authority_from_category(source.category)
    freshness = _freshness(source.collected_at, current_time)
    proximity = _proximity(source)
    independence = 1.0 if source.is_independent else (0.3 if source.is_official else 0.6)
    officialness = 1.0 if source.is_official or _looks_official(source.url) else 0.35
    terms = 1.0 if source.terms_allowed else 0.0
    robots = 1.0 if source.robots_allowed else 0.0
    duplication_penalty = min(1.0, source.duplicate_count * 0.15)
    marketing_penalty = source.marketing_language_ratio
    claim_support = source.claim_support_ratio
    combined = (
        authority * 0.18
        + freshness * 0.12
        + proximity * 0.10
        + independence * 0.08
        + officialness * 0.14
        + terms * 0.10
        + robots * 0.10
        + claim_support * 0.14
        - duplication_penalty * 0.07
        - marketing_penalty * 0.07
    )
    reasons = []
    if officialness >= 0.9:
        reasons.append("official_source")
    if independence >= 0.9:
        reasons.append("independent_confirmation")
    if terms == 0.0 or robots == 0.0:
        reasons.append("compliance_blocked")
    if claim_support < 0.5:
        reasons.append("weak_claim_support")
    return SourceQualityScore(
        authority_score=round(authority, 4),
        freshness_score=round(freshness, 4),
        proximity_score=round(proximity, 4),
        independence_score=round(independence, 4),
        officialness_score=round(officialness, 4),
        terms_compliance_score=round(terms, 4),
        robots_compliance_score=round(robots, 4),
        duplication_penalty=round(duplication_penalty, 4),
        marketing_bias_penalty=round(marketing_penalty, 4),
        claim_support_score=round(claim_support, 4),
        combined_score=round(max(0.0, min(1.0, combined)), 4),
        reasons=reasons,
    )


def source_supports_critical_claim(score: SourceQualityScore) -> bool:
    if score.terms_compliance_score < 1.0 or score.robots_compliance_score < 1.0:
        return False
    if score.officialness_score >= 0.9 and score.claim_support_score >= 0.8:
        return True
    return score.independence_score >= 0.8 and score.claim_support_score >= 0.7


def _authority_from_category(category: SourceCategory) -> float:
    weights = {
        SourceCategory.OFFICIAL_SITE: 1.0,
        SourceCategory.NVIDIA_OFFICIAL: 1.0,
        SourceCategory.NVIDIA_DOCS: 1.0,
        SourceCategory.OFFICIAL_BLOG: 0.9,
        SourceCategory.PRODUCT_DOCS: 0.85,
        SourceCategory.INVESTOR_PORTFOLIO: 0.75,
        SourceCategory.CAREERS: 0.75,
        SourceCategory.GITHUB_PUBLIC: 0.7,
        SourceCategory.LINKEDIN_PUBLIC: 0.7,
        SourceCategory.TRUSTED_NEWS: 0.65,
        SourceCategory.ACCELERATOR: 0.65,
        SourceCategory.STARTUP_DIRECTORY: 0.55,
        SourceCategory.CASE_MATERIAL: 0.8,
    }
    return weights.get(category, 0.5)


def _freshness(collected_at: datetime | None, now: datetime) -> float:
    if collected_at is None:
        return 0.5
    if collected_at.tzinfo is None:
        collected_at = collected_at.replace(tzinfo=UTC)
    days = max(0, (now.astimezone(UTC) - collected_at.astimezone(UTC)).days)
    if days <= 30:
        return 1.0
    if days <= 180:
        return 0.8
    if days <= 365:
        return 0.6
    return 0.3


def _proximity(source: SourceQualityInput) -> float:
    if source.is_official:
        return 1.0
    if source.category in {SourceCategory.PRODUCT_DOCS, SourceCategory.CAREERS, SourceCategory.GITHUB_PUBLIC}:
        return 0.75
    if source.category in {SourceCategory.TRUSTED_NEWS, SourceCategory.INVESTOR_PORTFOLIO}:
        return 0.6
    return 0.45


def _looks_official(url: str) -> bool:
    host = urlparse(url).netloc.casefold()
    return host.startswith("www.") or any(token in host for token in ("nvidia.com", ".gov", ".edu"))
