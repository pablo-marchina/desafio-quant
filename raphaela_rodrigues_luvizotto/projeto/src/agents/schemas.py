from __future__ import annotations

from pydantic import BaseModel, Field


class RecommendationOption(BaseModel):
    product: str
    fit_score: float | None = None
    reason: str
    citations: list[str] = Field(default_factory=list)


class LlmJudgment(BaseModel):
    label: str = "uncertain"
    score: float | None = None
    rationale: str | None = None
    signals: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    recommendations: list[RecommendationOption] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
