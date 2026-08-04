"""temporal RAG

Hypothesis: Evaluate whether temporal RAG improves final product output without paid dependency.
Category: 8.39 Temporal RAG and Currentness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from datetime import UTC
from typing import Any

from src.rag.schemas import RetrievedContext


class TemporalRag:
    """temporal RAG"""

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

                    days_ago = (now - dt).days

                    recency = max(0.0, 1.0 - days_ago / 730.0)

                    ctx.relevance_score = min(1.0, ctx.relevance_score * 0.5 + recency * 0.5)

                except (ValueError, TypeError):
                    pass

        contexts.sort(key=lambda c: c.relevance_score, reverse=True)

        return contexts
