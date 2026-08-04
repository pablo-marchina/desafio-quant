from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class DomainSpecificCrawler:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        target_domains = self.config.get("target_domains", ["nvidia.com", "developer.nvidia.com"])
        for ctx in contexts:
            url_lower = (ctx.url or "").lower()

            match_depth = sum(1 for d in target_domains if d in url_lower)

            if match_depth:
                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.15 * match_depth)

        return contexts
