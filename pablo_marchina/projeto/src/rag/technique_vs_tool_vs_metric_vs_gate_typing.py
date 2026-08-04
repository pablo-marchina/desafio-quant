"""technique vs tool vs metric vs gate typing

Hypothesis: Evaluate whether technique vs tool vs metric vs gate typing improves final product output without paid dependency.
Category: 8.46 Decision Accountability
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class TechniqueVsToolVsMetricVsGateTyping:
    """technique vs tool vs metric vs gate typing"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        typing_map = {
            "technique": ["method", "approach", "strategy"],
            "tool": ["library", "sdk", "platform", "service"],
            "metric": ["score", "rate", "percentage", "count"],
            "gate": ["check", "threshold", "condition", "guard"],
        }

        for ctx in contexts:
            text_lower = ctx.content.lower()

            for _ctype, keywords in typing_map.items():
                if any(k in text_lower for k in keywords):
                    ctx.relevance_score = min(1.0, ctx.relevance_score + 0.03)

        return contexts
