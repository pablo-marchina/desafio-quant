from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SeededReproducibilityMatrix:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        seeds_used: dict[str, int] = {}
        for ctx in contexts:
            seed_key = f"{ctx.source_id}:{ctx.chunk_id}"

            seeds_used[seed_key] = seeds_used.get(seed_key, 0) + 1

            ctx.relevance_score = min(1.0, ctx.relevance_score + 0.01)

        return contexts
