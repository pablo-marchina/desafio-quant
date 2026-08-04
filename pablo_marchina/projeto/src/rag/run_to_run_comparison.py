from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RunToRunComparison:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._previous_scores: dict[str, float] = {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            for ctx in contexts:
                prev = self._previous_scores.get(ctx.chunk_id)

                if prev is not None:
                    diff = ctx.relevance_score - prev

                    if abs(diff) > 0.2:
                        ctx.relevance_score = round(prev + 0.5 * diff, 4)

                        self._previous_scores[ctx.chunk_id] = ctx.relevance_score

        return contexts
