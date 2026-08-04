"""evidence-first final answer

Hypothesis: Evaluate whether evidence-first final answer improves final product output without paid dependency.
Category: 8.44 Output Versioning and Audit
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class EvidenceFirstFinalAnswer:
    """evidence-first final answer"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            if ctx.url or ctx.source_id:
                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.08)

            else:
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.05)

        contexts.sort(key=lambda c: c.relevance_score, reverse=True)

        return contexts
