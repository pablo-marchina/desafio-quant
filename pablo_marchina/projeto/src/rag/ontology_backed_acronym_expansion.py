"""ontology-backed acronym expansion

Hypothesis: Evaluate whether ontology-backed acronym expansion improves final product output without paid dependency.
Category: 8.50 Terminology and Domain Adaptation
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class OntologyBackedAcronymExpansion:
    """ontology-backed acronym expansion"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        import re as _re

        if not getattr(self, "_ontology", None):
            self._ontology: dict[str, dict] = {
                "rag": {"full": "Retrieval Augmented Generation", "domain": "nlp", "confidence": 0.95},
                "llm": {"full": "Large Language Model", "domain": "nlp", "confidence": 0.95},
                "gpu": {"full": "Graphics Processing Unit", "domain": "hardware", "confidence": 0.98},
                "cuda": {"full": "Compute Unified Device Architecture", "domain": "gpu", "confidence": 0.90},
            }

        for ctx in contexts:
            found = _re.findall(r"\b[A-Z]{2,}\b", ctx.content)

            for acronym in found:
                entry = self._ontology.get(acronym.lower())

                if entry and entry["confidence"] > 0.8:
                    ctx.relevance_score = min(1.0, ctx.relevance_score + entry["confidence"] * 0.02)

        return contexts
