from __future__ import annotations

from pydantic import BaseModel, Field

from src.sourcing.source_health import SourceAttempt


class SourceComplianceReport(BaseModel):
    robots_compliance_status: str
    tos_compliance_status: str
    compliant_sources: int = Field(ge=0)
    non_compliant_sources: int = Field(ge=0)
    blocked_sources: int = Field(ge=0)
    compliance_rate: float = Field(ge=0.0, le=1.0)


def summarize_compliance(
    attempts: list[SourceAttempt],
    *,
    robots_allowed_by_source: dict[str, bool],
    tos_allowed_by_source: dict[str, bool],
) -> SourceComplianceReport:
    compliant = 0
    non_compliant = 0
    for attempt in attempts:
        robots_ok = robots_allowed_by_source.get(attempt.source_id, False)
        tos_ok = tos_allowed_by_source.get(attempt.source_id, False)
        if robots_ok and tos_ok and not attempt.blocked:
            compliant += 1
        else:
            non_compliant += 1
    total = len(attempts)
    blocked = sum(1 for attempt in attempts if attempt.blocked)
    return SourceComplianceReport(
        robots_compliance_status="pass" if all(robots_allowed_by_source.values()) else "needs_review",
        tos_compliance_status="pass" if all(tos_allowed_by_source.values()) else "needs_review",
        compliant_sources=compliant,
        non_compliant_sources=non_compliant,
        blocked_sources=blocked,
        compliance_rate=round(compliant / total, 4) if total else 0.0,
    )
