"""Stop condition based on marginal new evidence — stop when marginal gain is low."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class StopConditionBasedOnMarginalNewEvidenceConfig(BaseModel):
    marginal_threshold: float = 0.02


class StopConditionBasedOnMarginalNewEvidence:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = StopConditionBasedOnMarginalNewEvidenceConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts
        seen_keywords: set[str] = set()
        result = []
        for ctx in contexts:
            words = {w.lower() for w in ctx.content.split() if len(w) > 3}
            new_words = words - seen_keywords
            marginal = len(new_words) / max(1, len(words))
            if marginal >= self.cfg.marginal_threshold:
                seen_keywords.update(new_words)
                result.append(ctx)
            else:
                ctx.relevance_score = round(max(0.0, ctx.relevance_score - 0.05), 4)
                result.append(ctx)
        return result
