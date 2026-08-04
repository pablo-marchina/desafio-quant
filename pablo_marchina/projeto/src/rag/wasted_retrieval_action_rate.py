"""wasted retrieval action rate

Hypothesis: Evaluate whether wasted retrieval action rate improves final product output without paid dependency.
Category: 8.49 Formal Agentic Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class WastedRetrievalActionRate:
    """wasted retrieval action rate"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_waste_log", None):
            self._waste_log: list[bool] = []

        low_score_count = sum(1 for c in contexts if c.relevance_score < 0.2)

        wasted = low_score_count > len(contexts) * 0.7

        self._waste_log.append(wasted)

        self._waste_log = self._waste_log[-100:]

        waste_rate = sum(self._waste_log) / max(len(self._waste_log), 1)

        for ctx in contexts:
            if waste_rate > 0.5:
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.05)

        return contexts
