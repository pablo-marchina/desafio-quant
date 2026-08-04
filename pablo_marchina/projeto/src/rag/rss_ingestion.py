from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RssIngestion:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._feeds: dict[str, list[str]] = {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        feed_url = kwargs.get("feed_url", "unknown")
        if feed_url not in self._feeds:
            self._feeds[feed_url] = []

            for ctx in contexts:
                self._feeds[feed_url].append(ctx.chunk_id)

                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.05)

                self._feeds[feed_url] = self._feeds[feed_url][-500:]
        return contexts
