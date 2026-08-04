from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field, HttpUrl

from src.sourcing.source_registry import SourceCategory


class SourceAttempt(BaseModel):
    source_id: str
    category: SourceCategory
    url: HttpUrl | None = None
    attempted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: str
    evidence_items: int = Field(default=0, ge=0)
    valid_claims: int = Field(default=0, ge=0)
    blocked_reason: str = ""
    latency_ms: float = Field(default=0.0, ge=0.0)
    cost_estimate: float = Field(default=0.0, ge=0.0)

    @property
    def successful(self) -> bool:
        return self.status == "success"

    @property
    def blocked(self) -> bool:
        return self.status == "blocked"


class SourceHealthReport(BaseModel):
    sources_attempted: int
    sources_successful: int
    blocked_sources: int
    valid_evidence_items: int
    source_success_rate: float = Field(ge=0.0, le=1.0)
    blocked_source_rate: float = Field(ge=0.0, le=1.0)
    evidence_yield_per_source: float = Field(ge=0.0)
    claim_support_per_source: float = Field(ge=0.0)
    source_cost_per_valid_claim: float = Field(ge=0.0)


def summarize_source_health(attempts: list[SourceAttempt]) -> SourceHealthReport:
    total = len(attempts)
    successful = sum(1 for attempt in attempts if attempt.successful)
    blocked = sum(1 for attempt in attempts if attempt.blocked)
    evidence_items = sum(attempt.evidence_items for attempt in attempts)
    valid_claims = sum(attempt.valid_claims for attempt in attempts)
    total_cost = sum(attempt.cost_estimate for attempt in attempts)
    return SourceHealthReport(
        sources_attempted=total,
        sources_successful=successful,
        blocked_sources=blocked,
        valid_evidence_items=evidence_items,
        source_success_rate=round(successful / total, 4) if total else 0.0,
        blocked_source_rate=round(blocked / total, 4) if total else 0.0,
        evidence_yield_per_source=round(evidence_items / total, 4) if total else 0.0,
        claim_support_per_source=round(valid_claims / total, 4) if total else 0.0,
        source_cost_per_valid_claim=round(total_cost / valid_claims, 4) if valid_claims else 0.0,
    )
