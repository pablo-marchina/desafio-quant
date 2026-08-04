from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class PlaywrightCrawler:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._crawled_pages: list[str] = []

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            page_url = ctx.url or ctx.source_id

            if page_url not in self._crawled_pages:
                self._crawled_pages.append(page_url)

                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.03)

                self._crawled_pages = self._crawled_pages[-500:]
        return contexts
