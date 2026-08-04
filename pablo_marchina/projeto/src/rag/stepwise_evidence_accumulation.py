from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class StepwiseEvidenceAccumulation:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            sorted_ctx = sorted(contexts, key=lambda x: x.relevance_score, reverse=True)
            cumulative_score = 0.0
            for i, ctx in enumerate(sorted_ctx):
                step_bonus = 1.0 + 0.05 * i

                ctx.relevance_score = round(ctx.relevance_score * step_bonus, 4)

                cumulative_score += ctx.relevance_score

        return contexts
