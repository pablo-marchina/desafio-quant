"""prompt regression test

Hypothesis: Evaluate whether prompt regression test improves final product output without paid dependency.
Category: 8.47 Tool/Flow/Prompt Governance
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class PromptRegressionTest:
    """prompt regression test"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_prompt_baseline", None):
            self._prompt_baseline: dict[str, float] = {}

        for ctx in contexts:
            prev = self._prompt_baseline.get(ctx.chunk_id, 0.5)

            diff = abs(ctx.relevance_score - prev)

            if diff > 0.2:
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.08)

            self._prompt_baseline[ctx.chunk_id] = ctx.relevance_score

        return contexts
