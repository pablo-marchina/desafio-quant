"""decision taxonomy

Hypothesis: Evaluate whether decision taxonomy improves final product output without paid dependency.
Category: 8.46 Decision Accountability
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class DecisionTaxonomy:
    """decision taxonomy"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_taxonomy", None):
            self._taxonomy: dict[str, list[str]] = {
                "approval": ["approved", "rejected", "pending"],
                "priority": ["critical", "high", "medium", "low"],
                "status": ["active", "blocked", "completed", "deferred"],
            }

        for ctx in contexts:
            found = 0

            for _cat, values in self._taxonomy.items():
                for v in values:
                    if v.lower() in ctx.content.lower():
                        found += 1

            if found:
                ctx.relevance_score = min(1.0, ctx.relevance_score + found * 0.02)

        return contexts
