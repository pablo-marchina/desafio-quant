"""risk taxonomy

Hypothesis: Evaluate whether risk taxonomy improves final product output without paid dependency.
Category: 8.46 Decision Accountability
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RiskTaxonomy:
    """risk taxonomy"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_risk_taxonomy", None):
            self._risk_taxonomy: dict[str, list[str]] = {
                "hallucination": ["confabulation", "unsupported claim", "made up"],
                "contradiction": ["contradict", "inconsistent", "conflicting"],
                "outdated": ["deprecated", "old", "legacy", "stale"],
            }

        for ctx in contexts:
            for _risk, signals in self._risk_taxonomy.items():
                if any(s in ctx.content.lower() for s in signals):
                    ctx.relevance_score = max(0.0, ctx.relevance_score - 0.04)

        return contexts
