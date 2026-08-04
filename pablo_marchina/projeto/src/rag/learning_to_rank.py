from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.rag.schemas import RetrievedContext


class LearningToRankConfig(BaseModel):
    enabled: bool = True
    feature_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "relevance": 0.4,
            "coverage": 0.2,
            "specificity": 0.15,
            "freshness": 0.1,
            "authority": 0.15,
        }
    )


class LearningToRank:
    def __init__(self, config: Any | None = None) -> None:
        self.config = LearningToRankConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            features = self._extract_features(ctx)

            score = self._compute_score(features)

            ctx.relevance_score = round(max(0.0, min(1.0, score)), 4)

            contexts.sort(key=lambda c: c.relevance_score, reverse=True)
        return contexts

    def _extract_features(self, ctx: RetrievedContext) -> dict[str, float]:
        content = ctx.content
        words = content.split()
        n_words = len(words)
        n_unique = len(set(words))
        return {
            "relevance": ctx.relevance_score,
            "coverage": min(n_words / 500.0, 1.0),
            "specificity": min(n_unique / max(n_words, 1) * 2.0, 1.0),
            "freshness": 0.5 if ctx.valid_from else 0.3,
            "authority": 0.5 if ctx.source_id and ctx.url else 0.2,
        }

    def _compute_score(self, features: dict[str, float]) -> float:
        score = 0.0
        for key, weight in self.config.feature_weights.items():
            score += weight * features.get(key, 0.0)
        return score
