"""stale source trap

Hypothesis: Evaluate whether stale source trap improves final product output without paid dependency.
Category: 8.39 Temporal RAG and Currentness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from datetime import UTC
from typing import Any

from src.rag.schemas import RetrievedContext


class StaleSourceTrap:
    """stale source trap"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        from datetime import datetime

        now = datetime.now(UTC)

        stale_days = self.config.get("stale_days", 180)

        for ctx in contexts:
            ts_str = ctx.collected_at or ctx.valid_from or ""

            if ts_str:
                try:
                    dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))

                    if (now - dt).days > stale_days:
                        ctx.relevance_score = max(0.0, ctx.relevance_score - 0.25)

                        ctx.freshness_policy = "stale"

                except (ValueError, TypeError):
                    pass

        return contexts
