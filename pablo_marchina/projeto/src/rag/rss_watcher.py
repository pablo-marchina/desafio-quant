from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RssWatcher:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._watched_feeds: dict[str, int] = {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        feed = kwargs.get("feed_url", "unknown")
        self._watched_feeds[feed] = self._watched_feeds.get(feed, 0) + 1
        for ctx in contexts:
            poll_count = self._watched_feeds.get(feed, 0)

            ctx.relevance_score = min(1.0, ctx.relevance_score + min(poll_count * 0.01, 0.2))

        return contexts
