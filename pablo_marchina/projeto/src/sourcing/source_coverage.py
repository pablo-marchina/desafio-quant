from __future__ import annotations

from pydantic import BaseModel, Field

from src.sourcing.source_compliance import summarize_compliance
from src.sourcing.source_health import SourceAttempt, summarize_source_health
from src.sourcing.source_registry import SourceCategory


class SourceCoverageReport(BaseModel):
    startup_id: str
    sources_attempted: int = Field(ge=0)
    sources_successful: int = Field(ge=0)
    blocked_sources: int = Field(ge=0)
    valid_evidence_items: int = Field(ge=0)
    coverage_by_category: dict[str, float]
    source_coverage_score: float = Field(ge=0.0, le=1.0)
    source_diversity_score: float = Field(ge=0.0, le=1.0)
    source_authority_score: float = Field(ge=0.0, le=1.0)
    freshness_score: float = Field(ge=0.0, le=1.0)
    blocked_source_rate: float = Field(ge=0.0, le=1.0)
    source_success_rate: float = Field(ge=0.0, le=1.0)
    evidence_yield_per_source: float = Field(ge=0.0)
    claim_support_per_source: float = Field(ge=0.0)
    cross_source_confirmation_rate: float = Field(ge=0.0, le=1.0)
    source_cost_per_valid_claim: float = Field(ge=0.0)
    robots_compliance_status: str
    tos_compliance_status: str
    remaining_gaps: list[str]


def compute_source_coverage(
    *,
    startup_id: str,
    attempts: list[SourceAttempt],
    expected_categories: set[SourceCategory] | None = None,
    category_authority_weights: dict[SourceCategory, float] | None = None,
    freshness_score: float = 1.0,
    cross_source_confirmed_claims: int = 0,
    total_claims: int = 0,
    robots_allowed_by_source: dict[str, bool] | None = None,
    tos_allowed_by_source: dict[str, bool] | None = None,
) -> SourceCoverageReport:
    expected = expected_categories or set(SourceCategory)
    weights = category_authority_weights or {category: 1.0 for category in expected}
    health = summarize_source_health(attempts)
    successful_categories = {attempt.category for attempt in attempts if attempt.successful}
    coverage_by_category = {
        category.value: (1.0 if category in successful_categories else 0.0)
        for category in sorted(expected, key=lambda item: item.value)
    }
    weighted_possible = sum(weights.get(category, 1.0) for category in expected)
    weighted_success = sum(weights.get(category, 1.0) for category in successful_categories if category in expected)
    source_coverage_score = round(weighted_success / weighted_possible, 4) if weighted_possible else 0.0
    source_diversity_score = round(len(successful_categories & expected) / len(expected), 4) if expected else 0.0
    source_authority_score = source_coverage_score
    compliance = summarize_compliance(
        attempts,
        robots_allowed_by_source=robots_allowed_by_source or {attempt.source_id: True for attempt in attempts},
        tos_allowed_by_source=tos_allowed_by_source or {attempt.source_id: True for attempt in attempts},
    )
    return SourceCoverageReport(
        startup_id=startup_id,
        sources_attempted=health.sources_attempted,
        sources_successful=health.sources_successful,
        blocked_sources=health.blocked_sources,
        valid_evidence_items=health.valid_evidence_items,
        coverage_by_category=coverage_by_category,
        source_coverage_score=source_coverage_score,
        source_diversity_score=source_diversity_score,
        source_authority_score=source_authority_score,
        freshness_score=round(max(0.0, min(1.0, freshness_score)), 4),
        blocked_source_rate=health.blocked_source_rate,
        source_success_rate=health.source_success_rate,
        evidence_yield_per_source=health.evidence_yield_per_source,
        claim_support_per_source=health.claim_support_per_source,
        cross_source_confirmation_rate=(
            round(cross_source_confirmed_claims / total_claims, 4) if total_claims else 0.0
        ),
        source_cost_per_valid_claim=health.source_cost_per_valid_claim,
        robots_compliance_status=compliance.robots_compliance_status,
        tos_compliance_status=compliance.tos_compliance_status,
        remaining_gaps=[
            category.value for category in sorted(expected - successful_categories, key=lambda item: item.value)
        ],
    )
