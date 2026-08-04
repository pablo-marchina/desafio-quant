"""correction memory

Hypothesis: Evaluate whether correction memory improves final product output without paid dependency.
Category: 8.43 Memory and Negative Learning
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class CorrectionMemory:
    """correction memory"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_corrections", None):
            self._corrections: list[str] = []

        for ctx in contexts:
            for corr in self._corrections:
                if corr.lower() in ctx.content.lower():
                    ctx.relevance_score = max(0.0, ctx.relevance_score - 0.15)

        if "corrected_text" in kwargs:
            self._corrections.append(str(kwargs["corrected_text"]))

        return contexts
