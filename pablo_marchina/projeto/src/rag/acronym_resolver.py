"""acronym resolver

Hypothesis: Evaluate whether acronym resolver improves final product output without paid dependency.
Category: 8.50 Terminology and Domain Adaptation
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class AcronymResolver:
    """acronym resolver"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        import re as _re

        if not getattr(self, "_acronyms", None):
            self._acronyms: dict[str, str] = {
                "rag": "Retrieval Augmented Generation",
                "llm": "Large Language Model",
                "gpu": "Graphics Processing Unit",
                "cpu": "Central Processing Unit",
                "api": "Application Programming Interface",
                "sdk": "Software Development Kit",
                "cuda": "Compute Unified Device Architecture",
                "tpu": "Tensor Processing Unit",
            }

        for ctx in contexts:
            found = _re.findall(r"\b[A-Z]{2,}\b", ctx.content)

            resolved = sum(1 for a in found if a.lower() in self._acronyms)

            if resolved:
                ctx.relevance_score = min(1.0, ctx.relevance_score + resolved * 0.025)

        return contexts
