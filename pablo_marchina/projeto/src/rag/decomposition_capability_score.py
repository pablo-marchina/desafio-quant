"""Decomposition capability score — score decomposition capability."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class DecompositionCapabilityScoreConfig(BaseModel):
    decomposition_weight: float = 0.3


class DecompositionCapabilityScore:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = DecompositionCapabilityScoreConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            gap_count = len(ctx.gap_types)

            sentences = max(1, ctx.content.count("."))

            decomposable = min(1.0, (gap_count * 0.2 + sentences * 0.01))

            ctx.relevance_score = round(
                (1.0 - self.cfg.decomposition_weight) * ctx.relevance_score
                + self.cfg.decomposition_weight * decomposable,
                4,
            )

        return contexts
