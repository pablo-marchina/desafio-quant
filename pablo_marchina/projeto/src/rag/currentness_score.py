"""currentness score

Hypothesis: Evaluate whether currentness score improves final product output without paid dependency.
Category: 8.38 Source Acquisition and Freshness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from datetime import UTC
from typing import Any

from src.rag.schemas import RetrievedContext


class CurrentnessScore:
    """currentness score"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        import re as _re
        from datetime import datetime

        now = datetime.now(UTC)

        current_year = now.year

        for ctx in contexts:
            years_found = _re.findall(r"(20\d{2})", ctx.content)

            if years_found:
                recent_years = sum(1 for y in years_found if int(y) >= current_year - 2)

                ctx.relevance_score = min(1.0, ctx.relevance_score + recent_years * 0.05)

            if ctx.valid_from:
                try:
                    dt = datetime.fromisoformat(ctx.valid_from.replace("Z", "+00:00"))

                    ctx.relevance_score = min(1.0, ctx.relevance_score + max(0, (dt.year - 2022)) * 0.03)

                except (ValueError, TypeError):
                    pass

        return contexts
