"""capability taxonomy

Hypothesis: Evaluate whether capability taxonomy improves final product output without paid dependency.
Category: 8.46 Decision Accountability
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class CapabilityTaxonomy:
    """capability taxonomy"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_cap_taxonomy", None):
            self._cap_taxonomy: dict[str, list[str]] = {
                "retrieval": ["search", "query", "fetch", "retrieve"],
                "generation": ["generate", "synthesize", "produce", "create"],
                "verification": ["verify", "validate", "check", "confirm"],
            }

        for ctx in contexts:
            for _cap, keywords in self._cap_taxonomy.items():
                if any(k in ctx.content.lower() for k in keywords):
                    ctx.relevance_score = min(1.0, ctx.relevance_score + 0.02)

        return contexts
