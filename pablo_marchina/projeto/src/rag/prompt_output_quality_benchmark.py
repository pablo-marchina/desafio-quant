"""prompt output quality benchmark

Hypothesis: Evaluate whether prompt output quality benchmark improves final product output without paid dependency.
Category: 8.47 Tool/Flow/Prompt Governance
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class PromptOutputQualityBenchmark:
    """prompt output quality benchmark"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        quality_terms = {"accurate", "clear", "concise", "relevant", "complete", "correct", "well-structured"}

        for ctx in contexts:
            quality_count = sum(1 for q in quality_terms if q in ctx.content.lower())

            ctx.relevance_score = min(1.0, ctx.relevance_score + quality_count * 0.03)

        return contexts
