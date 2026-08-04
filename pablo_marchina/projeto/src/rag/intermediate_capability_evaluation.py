"""Intermediate capability evaluation — evaluate intermediate capabilities."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class IntermediateCapabilityEvaluationConfig(BaseModel):
    query_alignment_weight: float = 0.4


class IntermediateCapabilityEvaluation:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = IntermediateCapabilityEvaluationConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query = kwargs.get("query", "")
        if not query:
            return contexts

            for ctx in contexts:
                query_words = set(query.lower().split())

                content_words = set(ctx.content.lower().split())

                overlap = len(query_words & content_words) / max(1, len(query_words))

                ctx.relevance_score = round(
                    (1.0 - self.cfg.query_alignment_weight) * ctx.relevance_score
                    + self.cfg.query_alignment_weight * overlap,
                    4,
                )

        return contexts
