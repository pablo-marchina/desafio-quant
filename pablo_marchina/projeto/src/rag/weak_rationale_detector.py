"""weak-rationale detector

Hypothesis: Evaluate whether weak-rationale detector improves final product output without paid dependency.
Category: 8.43 Memory and Negative Learning
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class WeakRationaleDetector:
    """weak-rationale detector"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        weak_indicators = ["because", "since", "due to", "therefore", "thus"]
        for ctx in contexts:
            sentences = [s.strip() for s in ctx.content.split(".") if s.strip()]

            weak_count = 0.0

            for s in sentences:
                words = s.lower().split()

                if len(words) < 5:
                    weak_count += 1

                elif not any(i in words for i in weak_indicators):
                    weak_count += 0.5

            if sentences:
                weak_ratio = weak_count / len(sentences)

                if weak_ratio > 0.5:
                    ctx.relevance_score = max(0.0, ctx.relevance_score - weak_ratio * 0.1)

        return contexts
