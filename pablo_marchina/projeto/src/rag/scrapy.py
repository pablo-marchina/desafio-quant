from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class Scrapy:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._items: list[dict[str, Any]] = []

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            self._items.append(
                {
                    "source": ctx.source_id,
                    "title": ctx.title,
                    "score": ctx.relevance_score,
                    "content_len": len(ctx.content),
                }
            )

            self._items = self._items[-500:]
        return contexts
