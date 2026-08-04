"""expensive model escalation gate

Hypothesis: Evaluate whether expensive model escalation gate improves final product output without paid dependency.
Category: 8.21 Model Serving and Routing
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ExpensiveModelEscalationGate:
    """expensive model escalation gate"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        escalation_threshold = self.config.get("escalation_threshold", 0.7)
        for ctx in contexts:
            if ctx.relevance_score >= escalation_threshold:
                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.1)

        return contexts
