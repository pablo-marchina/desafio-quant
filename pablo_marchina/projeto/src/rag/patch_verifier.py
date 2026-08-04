"""patch verifier

Hypothesis: Evaluate whether patch verifier improves final product output without paid dependency.
Category: 8.48 Software V and V
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class PatchVerifier:
    """patch verifier"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            patch_markers = ["---", "+++", "@@", "-", "+", "diff --git"]

            patch_count = sum(1 for m in patch_markers if m in ctx.content)

            if patch_count >= 3:
                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.1)

            verify_terms = ["verified", "tested", "confirmed", "validated"]

            if any(v in ctx.content.lower() for v in verify_terms):
                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.05)

        return contexts
