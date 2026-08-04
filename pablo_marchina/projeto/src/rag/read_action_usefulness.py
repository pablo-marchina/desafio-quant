"""read action usefulness

Hypothesis: Evaluate whether read action usefulness improves final product output without paid dependency.
Category: 8.49 Formal Agentic Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ReadActionUsefulness:
    """read action usefulness"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_read_results", None):
            self._read_results: list[float] = []

        avg = sum(c.relevance_score for c in contexts) / max(len(contexts), 1)

        self._read_results.append(avg)

        self._read_results = self._read_results[-50:]

        for ctx in contexts:
            if avg > 0.4:
                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.03)

        return contexts
