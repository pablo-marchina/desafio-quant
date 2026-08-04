from __future__ import annotations

from pydantic import BaseModel, Field

from src.sourcing.source_health import SourceAttempt
from src.sourcing.source_registry import SourceRecord


class SourceScore(BaseModel):
    source_id: str
    source_authority_score: float = Field(ge=0.0, le=1.0)
    freshness_score: float = Field(ge=0.0, le=1.0)
    evidence_yield_score: float = Field(ge=0.0, le=1.0)
    compliance_score: float = Field(ge=0.0, le=1.0)
    overall_score: float = Field(ge=0.0, le=1.0)
    features: dict[str, float]
    weights: dict[str, float]
    confidence: float = Field(ge=0.0, le=1.0)
    uncertainty: float = Field(ge=0.0, le=1.0)


def score_source(
    source: SourceRecord,
    attempt: SourceAttempt,
    *,
    freshness_days: int,
    robots_allowed: bool,
    tos_allowed: bool,
) -> SourceScore:
    freshness_score = max(0.0, min(1.0, 1.0 - (freshness_days / 365.0)))
    evidence_yield_score = min(1.0, attempt.evidence_items / 10.0)
    compliance_score = 1.0 if robots_allowed and tos_allowed and not attempt.blocked else 0.0
    weights = {
        "authority": 0.35,
        "freshness": 0.20,
        "evidence_yield": 0.25,
        "compliance": 0.20,
    }
    features = {
        "authority": source.authority_weight,
        "freshness": freshness_score,
        "evidence_yield": evidence_yield_score,
        "compliance": compliance_score,
    }
    overall = sum(features[name] * weight for name, weight in weights.items())
    confidence = min(1.0, 0.4 + evidence_yield_score * 0.4 + compliance_score * 0.2)
    return SourceScore(
        source_id=source.source_id,
        source_authority_score=round(source.authority_weight, 4),
        freshness_score=round(freshness_score, 4),
        evidence_yield_score=round(evidence_yield_score, 4),
        compliance_score=round(compliance_score, 4),
        overall_score=round(overall, 4),
        features={key: round(value, 4) for key, value in features.items()},
        weights=weights,
        confidence=round(confidence, 4),
        uncertainty=round(1.0 - confidence, 4),
    )
