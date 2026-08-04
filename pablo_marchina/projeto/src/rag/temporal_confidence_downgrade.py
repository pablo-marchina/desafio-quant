"""temporal confidence downgrade

Hypothesis: Evaluate whether temporal confidence downgrade improves final product output without paid dependency.
Category: 8.39 Temporal RAG and Currentness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.rag.schemas import RetrievedContext


class TemporalConfidenceDowngrade:
    """temporal confidence downgrade — reduce score for contexts with stale timestamps."""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

        max_age_days = kwargs.get("max_age_days", 365)
        now = datetime.now(UTC)
        for ctx in contexts:
            ts_str = ctx.valid_from or ""

            if ts_str:
                try:
                    dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))

                    age_days = (now - dt).days

                    if age_days > max_age_days:
                        downgrade = min(0.5, (age_days - max_age_days) * 0.001)

                        ctx.relevance_score = max(0.0, ctx.relevance_score - downgrade)

                    elif age_days < 30:
                        ctx.relevance_score = min(1.0, ctx.relevance_score + 0.05)

                except (ValueError, TypeError):
                    ctx.relevance_score = max(0.0, ctx.relevance_score - 0.1)

                else:
                    ctx.relevance_score = max(0.0, ctx.relevance_score - 0.05)

        return contexts
