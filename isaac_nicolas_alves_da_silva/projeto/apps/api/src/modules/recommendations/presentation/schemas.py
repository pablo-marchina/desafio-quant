"""Schemas Pydantic do modulo recommendations."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from apps.api.src.modules.recommendations.application.dto import (
    RecommendationView,
    TechnologyStatView,
    TechnologyStatsView,
)


class GenerateRecommendationsRequest(BaseModel):
    startup_id: UUID


class ReviewRecommendationRequest(BaseModel):
    status: str
    comment: str | None = None
    reviewed_by: str | None = None


class RecommendationResponse(BaseModel):
    id: UUID
    startup_id: UUID
    technology_slug: str
    technology_name: str
    category: str
    score: float
    confidence: float
    complexity: str
    priority: int
    justification: str
    matched_keywords: list[str]
    evidence_ids: list[UUID]
    signal_origins: list[str]
    missing_signals: list[str]
    nivel: str
    faltando: list[str]
    review_status: str
    review_comment: str | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    created_at: datetime

    @classmethod
    def from_view(cls, view: RecommendationView) -> "RecommendationResponse":
        return cls(
            id=view.id,
            startup_id=view.startup_id,
            technology_slug=view.technology_slug,
            technology_name=view.technology_name,
            category=view.category,
            score=view.score,
            confidence=view.confidence,
            complexity=view.complexity,
            priority=view.priority,
            justification=view.justification,
            matched_keywords=view.matched_keywords,
            evidence_ids=view.evidence_ids,
            signal_origins=view.signal_origins,
            missing_signals=view.missing_signals,
            nivel=view.nivel,
            faltando=view.faltando,
            review_status=view.review_status,
            review_comment=view.review_comment,
            reviewed_by=view.reviewed_by,
            reviewed_at=view.reviewed_at,
            created_at=view.created_at,
        )


class TechnologyStatResponse(BaseModel):
    technology_slug: str
    technology_name: str
    count: int

    @classmethod
    def from_view(cls, view: TechnologyStatView) -> "TechnologyStatResponse":
        return cls(
            technology_slug=view.technology_slug,
            technology_name=view.technology_name,
            count=view.count,
        )


class TechnologyStatsResponse(BaseModel):
    items: list[TechnologyStatResponse]

    @classmethod
    def from_view(cls, view: TechnologyStatsView) -> "TechnologyStatsResponse":
        return cls(items=[TechnologyStatResponse.from_view(item) for item in view.items])
