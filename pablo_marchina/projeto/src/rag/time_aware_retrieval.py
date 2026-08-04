"""time-aware retrieval

Hypothesis: Evaluate whether time-aware retrieval improves final product output without paid dependency.
Category: 8.39 Temporal RAG and Currentness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from datetime import UTC
from typing import Any

from src.rag.schemas import RetrievedContext


class TimeAwareRetrieval:
    """time-aware retrieval"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        from datetime import datetime

        now = datetime.now(UTC)

        time_ref = kwargs.get("reference_date", "")

        reference = datetime.fromisoformat(time_ref.replace("Z", "+00:00")) if time_ref else now

        for ctx in contexts:
            ts_str = ctx.valid_from or ctx.collected_at or ""

            if ts_str:
                try:
                    dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))

                    if dt <= reference:
                        ctx.relevance_score = min(1.0, ctx.relevance_score + 0.1)

                    else:
                        ctx.relevance_score = max(0.0, ctx.relevance_score - 0.1)

                except (ValueError, TypeError):
                    pass

        return contexts
