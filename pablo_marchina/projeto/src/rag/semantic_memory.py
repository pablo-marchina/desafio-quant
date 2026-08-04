"""semantic memory

Hypothesis: Evaluate whether semantic memory improves final product output without paid dependency.
Category: 8.43 Memory and Negative Learning
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SemanticMemory:
    """semantic memory"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_concepts", None):
            self._concepts: dict[str, float] = {}

        for ctx in contexts:
            matched = sum(1 for c in self._concepts if c.lower() in ctx.content.lower())

            if matched:
                ctx.relevance_score = min(1.0, ctx.relevance_score + matched * 0.02)

        for w in " ".join(c.content for c in contexts).split():
            wc = w.strip(".,!?;:").lower()

            if len(wc) > 4:
                self._concepts[wc] = self._concepts.get(wc, 0.0) + 0.01

        return contexts
