"""copy-preserving editing

Hypothesis: Evaluate whether copy-preserving editing improves final product output without paid dependency.
Category: 8.44 Output Versioning and Audit
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class CopyPreservingEditing:
    """copy-preserving editing"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_preserved_blocks", None):
            self._preserved_blocks: dict[str, list[str]] = {}

        for ctx in contexts:
            key = ctx.chunk_id

            if key not in self._preserved_blocks:
                self._preserved_blocks[key] = ctx.content.split(". ")

            current_blocks = ctx.content.split(". ")

            preserved = sum(1 for b in current_blocks if b in self._preserved_blocks.get(key, []))

            if preserved > 0:
                ctx.relevance_score = min(1.0, ctx.relevance_score + preserved * 0.01)

        return contexts
