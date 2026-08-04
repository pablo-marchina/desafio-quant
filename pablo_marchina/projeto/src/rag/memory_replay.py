"""memory replay

Hypothesis: Evaluate whether memory replay improves final product output without paid dependency.
Category: 8.43 Memory and Negative Learning
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class MemoryReplay:
    """memory replay"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_replay_buffer", None):
            self._replay_buffer: list[dict] = []

        query = kwargs.get("query", "")

        if query:
            self._replay_buffer.append({"query": query.lower(), "count": len(contexts)})

        self._replay_buffer = self._replay_buffer[-30:]

        for ctx in contexts:
            for past in self._replay_buffer:
                if any(w in ctx.content.lower() for w in past["query"].split()):
                    ctx.relevance_score = min(1.0, ctx.relevance_score + 0.03)

        return contexts
