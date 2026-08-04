"""decision memory

Hypothesis: Evaluate whether decision memory improves final product output without paid dependency.
Category: 8.43 Memory and Negative Learning
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class DecisionMemory:
    """decision memory"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_decisions", None):
            self._decisions: list[dict] = []

        for ctx in contexts:
            for d in self._decisions:
                if any(t.lower() in ctx.content.lower() for t in d.get("topics", [])):
                    ctx.relevance_score = min(1.0, ctx.relevance_score + 0.04)

        if "decision_topic" in kwargs:
            self._decisions.append(
                {"topics": str(kwargs["decision_topic"]).split(","), "outcome": kwargs.get("outcome")}
            )

        self._decisions = self._decisions[-100:]

        return contexts
