"""archived page snapshot

Hypothesis: Evaluate whether archived page snapshot improves final product output without paid dependency.
Category: 8.38 Source Acquisition and Freshness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ArchivedPageSnapshot:
    """archived page snapshot"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        archive_indicators = ["web.archive.org", "archive.is", "cached", "snapshot", "cached version"]

        for ctx in contexts:
            url_lower = (ctx.url or "").lower()

            if any(a in url_lower for a in archive_indicators):
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.05)

        return contexts
