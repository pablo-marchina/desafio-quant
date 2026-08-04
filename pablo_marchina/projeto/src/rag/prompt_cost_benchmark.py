"""prompt cost benchmark

Hypothesis: Evaluate whether prompt cost benchmark improves final product output without paid dependency.
Category: 8.47 Tool/Flow/Prompt Governance
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class PromptCostBenchmark:
    """prompt cost benchmark"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            token_estimate = len(ctx.content.split())

            cost_estimate = token_estimate * 0.002

            cost_penalty = min(cost_estimate * 0.01, 0.2)

            ctx.relevance_score = max(0.0, ctx.relevance_score - cost_penalty)

        return contexts
