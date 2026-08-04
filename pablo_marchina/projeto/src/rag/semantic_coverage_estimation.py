"""semantic coverage estimation

Hypothesis: Evaluate whether semantic coverage estimation improves final product output without paid dependency.
Category: 8.45 Failure Transparency and Completeness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SemanticCoverageEstimation:
    """semantic coverage estimation"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_semantic_space", None):
            self._semantic_space: set[str] = set()

        for ctx in contexts:
            words = set(w.lower().strip(".,!?;:()") for w in ctx.content.split())

            self._semantic_space.update(words)

        len(self._semantic_space)

        for ctx in contexts:
            ctx_words = set(w.lower().strip(".,!?;:()") for w in ctx.content.split())

            novelty = len(ctx_words - self._semantic_space) / max(len(ctx_words), 1)

            if novelty > 0.3:
                ctx.relevance_score = min(1.0, ctx.relevance_score + novelty * 0.05)

        return contexts
