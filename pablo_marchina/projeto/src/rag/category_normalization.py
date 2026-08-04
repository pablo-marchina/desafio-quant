"""category normalization

Hypothesis: Evaluate whether category normalization improves final product output without paid dependency.
Category: 8.50 Terminology and Domain Adaptation
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class CategoryNormalization:
    """category normalization"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_category_map", None):
            self._category_map: dict[str, str] = {
                "deep learning": "deep_learning",
                "machine learning": "machine_learning",
                "nlp": "natural_language_processing",
                "cv": "computer_vision",
                "gen ai": "generative_ai",
                "genai": "generative_ai",
            }

        for ctx in contexts:
            normalized = 0

            for raw, _canon in self._category_map.items():
                if raw in ctx.content.lower():
                    normalized += 1

            if normalized:
                ctx.relevance_score = min(1.0, ctx.relevance_score + normalized * 0.02)

        return contexts
