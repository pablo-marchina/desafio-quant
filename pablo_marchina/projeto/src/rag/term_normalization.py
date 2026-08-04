"""term normalization

Hypothesis: Evaluate whether term normalization improves final product output without paid dependency.
Category: 8.50 Terminology and Domain Adaptation
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class TermNormalization:
    """term normalization"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_term_map", None):
            self._term_map: dict[str, str] = {
                "gpu": "graphics processing unit",
                "llm": "large language model",
                "rag": "retrieval augmented generation",
                "api": "application programming interface",
                "sdk": "software development kit",
                "mlops": "ml operations",
            }

        for ctx in contexts:
            norm_count = 0

            text_lower = ctx.content.lower()

            for abbr, _full in self._term_map.items():
                if abbr in text_lower:
                    norm_count += 1

            if norm_count:
                ctx.relevance_score = min(1.0, ctx.relevance_score + norm_count * 0.02)

        return contexts
