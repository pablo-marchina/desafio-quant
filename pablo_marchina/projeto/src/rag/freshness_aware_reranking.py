"""freshness-aware reranking

Hypothesis: Evaluate whether freshness-aware reranking improves final product output without paid dependency.
Category: 8.38 Source Acquisition and Freshness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from datetime import UTC
from typing import Any

from src.rag.schemas import RetrievedContext


class FreshnessAwareReranking:
    """freshness-aware reranking"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        from datetime import datetime

        now = datetime.now(UTC)

        for ctx in contexts:
            ts_str = ctx.valid_from or ctx.collected_at or ""

            if ts_str:
                try:
                    dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))

                    days_old = (now - dt).days

                    if days_old > 365:
                        ctx.relevance_score = max(0.0, ctx.relevance_score - 0.2)

                    elif days_old > 180:
                        ctx.relevance_score = max(0.0, ctx.relevance_score - 0.1)

                    elif days_old < 30:
                        ctx.relevance_score = min(1.0, ctx.relevance_score + 0.1)

                except (ValueError, TypeError):
                    pass

        contexts.sort(key=lambda c: c.relevance_score, reverse=True)

        return contexts
