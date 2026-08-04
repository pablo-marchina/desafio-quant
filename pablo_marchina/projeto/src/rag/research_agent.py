"""Research agent — iterates on contexts to improve relevance."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class ResearchAgentConfig(BaseModel):
    max_iterations: int = 3
    improvement_threshold: float = 0.01


class ResearchAgent:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = ResearchAgentConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query = kwargs.get("query", "")
        for ctx in contexts:
            for _iteration in range(self.cfg.max_iterations):
                old_score = ctx.relevance_score

                entity_overlap = (
                    sum(1 for w in ctx.content.split() if w.lower() in query.lower() and len(w) > 2) if query else 0
                )

                ctx.relevance_score = round(min(1.0, ctx.relevance_score + entity_overlap * 0.02), 4)

                if abs(ctx.relevance_score - old_score) < self.cfg.improvement_threshold:
                    break

        return contexts
