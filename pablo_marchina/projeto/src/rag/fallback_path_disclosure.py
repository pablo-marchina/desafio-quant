"""fallback path disclosure

Hypothesis: Evaluate whether fallback path disclosure improves final product output without paid dependency.
Category: 8.45 Failure Transparency and Completeness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class FallbackPathDisclosure:
    """fallback path disclosure"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_fallback_paths", None):
            self._fallback_paths: list[str] = []

        fallback = kwargs.get("fallback_used", "")

        if fallback:
            self._fallback_paths.append(fallback)

        was_fallback = bool(kwargs.get("fallback_used", ""))

        for ctx in contexts:
            if was_fallback:
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.05)

        return contexts
