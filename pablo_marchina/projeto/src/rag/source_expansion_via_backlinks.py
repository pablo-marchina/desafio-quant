"""source expansion via backlinks

Hypothesis: Evaluate whether source expansion via backlinks improves final product output without paid dependency.
Category: 8.38 Source Acquisition and Freshness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SourceExpansionViaBacklinks:
    """source expansion via backlinks"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_backlink_count", None):
            self._backlink_count: dict[str, int] = {}

        for ctx in contexts:
            domain = (ctx.url or "").split("/")[2] if ctx.url and "://" in ctx.url else "unknown"

            count = self._backlink_count.get(domain, 0)

            ctx.relevance_score = min(1.0, ctx.relevance_score + min(count * 0.01, 0.2))

            self._backlink_count[domain] = self._backlink_count.get(domain, 0) + 1

        return contexts
