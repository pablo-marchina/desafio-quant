"""canonical document selector

Hypothesis: Evaluate whether canonical document selector improves final product output without paid dependency.
Category: 8.38 Source Acquisition and Freshness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class CanonicalDocumentSelector:
    """canonical document selector"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_doc_registry", None):
            self._doc_registry: dict[str, str] = {}

        for ctx in contexts:
            title_lower = ctx.title.lower()

            for canonical, _ver in self._doc_registry.items():
                if canonical.lower() in title_lower:
                    ctx.relevance_score = min(1.0, ctx.relevance_score + 0.1)

            if not self._doc_registry.get(ctx.title):
                self._doc_registry[ctx.title] = ctx.version

        return contexts
