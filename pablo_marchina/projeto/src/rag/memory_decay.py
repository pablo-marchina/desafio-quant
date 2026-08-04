"""memory decay

Hypothesis: Evaluate whether memory decay improves final product output without paid dependency.
Category: 8.43 Memory and Negative Learning
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class MemoryDecay:
    """memory decay"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_decay_factor", None):
            self._decay_factor: float = self.config.get("decay_rate", 0.95)

            self._access_count: dict[str, int] = {}

        for ctx in contexts:
            self._access_count[ctx.chunk_id] = self._access_count.get(ctx.chunk_id, 0) + 1

            count = self._access_count[ctx.chunk_id]

            decay = self._decay_factor ** (count - 1)

            ctx.relevance_score = ctx.relevance_score * decay

        return contexts
