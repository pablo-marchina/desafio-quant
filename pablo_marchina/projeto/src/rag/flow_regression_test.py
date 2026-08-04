from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class FlowRegressionTest:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._baseline_scores: dict[str, float] = {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        regressions = []
        for ctx in contexts:
            baseline = self._baseline_scores.get(ctx.chunk_id)

            if baseline is not None and ctx.relevance_score < baseline - 0.1:
                regressions.append(ctx.chunk_id)

                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.1)

                self._baseline_scores[ctx.chunk_id] = ctx.relevance_score

        return contexts
