"""domain QA adaptation layer

Hypothesis: Evaluate whether domain QA adaptation layer improves final product output without paid dependency.
Category: 8.50 Terminology and Domain Adaptation
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class DomainQaAdaptationLayer:
    """domain QA adaptation layer"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_domain_patterns", None):
            self._domain_patterns: dict[str, list[str]] = {
                "startup": ["funding", "revenue", "team", "product", "market"],
                "ai_tech": ["model", "training", "inference", "dataset", "accuracy"],
                "nvidia": ["cuda", "tensorrt", "gpu", "h100", "a100", "nemotron"],
            }

        for ctx in contexts:
            for _domain, keywords in self._domain_patterns.items():
                kw_matches = sum(1 for k in keywords if k.lower() in ctx.content.lower())

                if kw_matches >= 2:
                    ctx.relevance_score = min(1.0, ctx.relevance_score + kw_matches * 0.02)

        return contexts
