"""minimal change revision

Hypothesis: Evaluate whether minimal change revision improves final product output without paid dependency.
Category: 8.44 Output Versioning and Audit
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class MinimalChangeRevision:
    """minimal change revision"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_original_content", None):
            self._original_content: dict[str, str] = {}

        for ctx in contexts:
            original = self._original_content.get(ctx.chunk_id, "")

            if original and original != ctx.content:
                change_ratio = 1.0 - (len(original) / max(len(ctx.content), 1))

                if change_ratio > 0.5:
                    ctx.relevance_score = max(0.0, ctx.relevance_score - 0.1)

            self._original_content[ctx.chunk_id] = ctx.content

        return contexts
