"""human annotation uncertainty modeling

Hypothesis: Evaluate whether human annotation uncertainty modeling improves
final product output without paid dependency.
Category: 8.41 Advanced Benchmarks and Research Artifacts
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class HumanAnnotationUncertaintyModeling:
    """human annotation uncertainty modeling — penalize contexts with high subjective/vague language."""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            uncertainty_markers = [
                "maybe",
                "perhaps",
                "possibly",
                "likely",
                "unlikely",
                "probably",
                "could be",
                "might be",
                "seems",
                "appears",
                "suggests",
                "indicates",
                "i think",
                "i believe",
                "in my opinion",
                "not sure",
                "unclear",
            ]
            agreement_threshold = kwargs.get("agreement_threshold", 0.7)
            for ctx in contexts:
                text_lower = ctx.content.lower()

                marker_count = sum(1 for m in uncertainty_markers if m in text_lower)

                sentence_count = max(len([s for s in ctx.content.split(".") if s.strip()]), 1)

                uncertainty_ratio = marker_count / sentence_count

                penalty = uncertainty_ratio * 0.3

                confidence = 1.0 - min(penalty, 0.8)

                disagreement_penalty = 0.0

                if confidence < agreement_threshold:
                    disagreement_penalty = (agreement_threshold - confidence) * 0.2

                    ctx.relevance_score = max(0.0, min(1.0, ctx.relevance_score * confidence - disagreement_penalty))

        return contexts
