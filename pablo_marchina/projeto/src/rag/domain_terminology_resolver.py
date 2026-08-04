"""domain terminology resolver

Hypothesis: Evaluate whether domain terminology resolver improves final product output without paid dependency.
Category: 8.50 Terminology and Domain Adaptation
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class DomainTerminologyResolver:
    """domain terminology resolver"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_domain_terms", None):
            self._domain_terms: dict[str, str] = {
                "ai": "Artificial Intelligence",
                "ml": "Machine Learning",
                "nlp": "Natural Language Processing",
                "rag": "Retrieval Augmented Generation",
                "llm": "Large Language Model",
                "gpu": "Graphics Processing Unit",
                "cuda": "Compute Unified Device Architecture",
                "tensorrt": "TensorRT",
            }

        for ctx in contexts:
            resolved_count = 0

            text = ctx.content

            for abbr, full in self._domain_terms.items():
                if abbr.lower() in text.lower() and full.lower() not in text.lower():
                    resolved_count += 1

            if resolved_count:
                ctx.relevance_score = min(1.0, ctx.relevance_score + resolved_count * 0.02)

        return contexts
