"""self-preference bias test

Hypothesis: Evaluate whether self-preference bias test improves final product output without paid dependency.
Category: 8.45 Failure Transparency and Completeness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SelfPreferenceBiasTest:
    """self-preference bias test"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            self_ref = sum(
                1
                for w in ["i believe", "i think", "my analysis", "in my view", "my assessment", "in my opinion"]
                if w.lower() in ctx.content.lower()
            )

            if self_ref:
                ctx.relevance_score = max(0.0, ctx.relevance_score - self_ref * 0.05)

        return contexts
