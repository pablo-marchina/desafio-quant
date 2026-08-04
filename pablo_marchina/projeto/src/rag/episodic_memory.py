"""episodic memory

Hypothesis: Evaluate whether episodic memory improves final product output without paid dependency.
Category: 8.43 Memory and Negative Learning
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class EpisodicMemory:
    """episodic memory"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_episodes", None):
            self._episodes: list[dict] = []

        query = kwargs.get("query", "")

        if query:
            self._episodes.append({"query": query, "count": len(contexts)})

            self._episodes = self._episodes[-50:]

        for ctx in contexts:
            for ep in self._episodes:
                if any(w in ctx.content.lower() for w in ep.get("query", "").lower().split()):
                    ctx.relevance_score = min(1.0, ctx.relevance_score + 0.05)

        return contexts
