from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SitemapDiscovery:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._discovered_urls: set[str] = set()

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            if ctx.url and ctx.url not in self._discovered_urls:
                self._discovered_urls.add(ctx.url)

                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.1)

        return contexts
