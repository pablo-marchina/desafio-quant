"""source freshness monitor

Hypothesis: Evaluate whether source freshness monitor improves final product output without paid dependency.
Category: 8.38 Source Acquisition and Freshness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from datetime import UTC
from typing import Any

from src.rag.schemas import RetrievedContext


class SourceFreshnessMonitor:
    """source freshness monitor"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        from datetime import datetime

        now = datetime.now(UTC)

        for ctx in contexts:
            if ctx.valid_until:
                try:
                    expiry = datetime.fromisoformat(ctx.valid_until.replace("Z", "+00:00"))

                    days_left = (expiry - now).days

                    if days_left < 0:
                        ctx.relevance_score = max(0.0, ctx.relevance_score - 0.3)

                    elif days_left < 30:
                        ctx.relevance_score = max(0.0, ctx.relevance_score - 0.1)

                except (ValueError, TypeError):
                    pass

        return contexts
