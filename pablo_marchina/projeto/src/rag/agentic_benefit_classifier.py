"""Agentic benefit classifier — classify if agentic RAG is beneficial."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class AgenticBenefitClassifierConfig(BaseModel):
    benefit_threshold: float = 0.5


class AgenticBenefitClassifier:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = AgenticBenefitClassifierConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            complexity = len(set(g for ctx in contexts for g in ctx.gap_types)) / max(1, len(contexts))
            score_var = 0.0
            if len(contexts) > 1:
                scores = [ctx.relevance_score for ctx in contexts]

                mean = sum(scores) / len(scores)

                score_var = sum((s - mean) ** 2 for s in scores) / len(scores)

                benefit_score = 0.5 * complexity + 0.5 * min(1.0, score_var * 5)
                for ctx in contexts:
                    if benefit_score > self.cfg.benefit_threshold:
                        ctx.relevance_score = round(min(1.0, ctx.relevance_score * 1.1), 4)

        return contexts
