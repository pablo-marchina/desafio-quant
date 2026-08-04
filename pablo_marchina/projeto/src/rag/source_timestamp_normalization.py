"""source timestamp normalization

Hypothesis: Evaluate whether source timestamp normalization improves final product output without paid dependency.
Category: 8.38 Source Acquisition and Freshness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SourceTimestampNormalization:
    """source timestamp normalization"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            ts = ctx.valid_from or ctx.collected_at or ""

            if ts:
                try:
                    from datetime import datetime

                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))

                    year_bonus = max(0, (dt.year - 2020)) * 0.02

                    ctx.relevance_score = min(1.0, ctx.relevance_score + year_bonus)

                except (ValueError, TypeError):
                    ctx.relevance_score = max(0.0, ctx.relevance_score - 0.05)

        return contexts
