"""Search-read-search loop — iterative search-read loop."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class SearchReadSearchLoopConfig(BaseModel):
    max_loops: int = 3


class SearchReadSearchLoop:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = SearchReadSearchLoopConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query = kwargs.get("query", "")
        for ctx in contexts:
            for _i in range(self.cfg.max_loops):
                old = ctx.relevance_score

                search_score = 0.3 * min(1.0, len(ctx.content) / 1000)

                read_score = (
                    0.4 * sum(1 for w in query.lower().split() if w in ctx.content.lower()) / max(1, len(query.split()))
                    if query
                    else 0
                )

                ctx.relevance_score = round(min(1.0, old + search_score * 0.3 + read_score * 0.3), 4)

                if abs(ctx.relevance_score - old) < 0.01:
                    break

        return contexts
