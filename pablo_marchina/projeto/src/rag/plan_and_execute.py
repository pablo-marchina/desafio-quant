"""Plan-and-execute — plan retrieval steps then execute."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class PlanAndExecuteConfig(BaseModel):
    plan_top_k: int = 5
    min_plan_score: float = 0.3


class PlanAndExecute:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = PlanAndExecuteConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        scored = []
        for ctx in contexts:
            length_score = min(1.0, len(ctx.content) / 2000)
            keyword_score = len(ctx.gap_types) * 0.1
            plan_score = 0.4 * ctx.relevance_score + 0.3 * length_score + 0.3 * keyword_score
            scored.append((plan_score, ctx))
        scored.sort(key=lambda x: x[0], reverse=True)
        selected = [ctx for score, ctx in scored if score >= self.cfg.min_plan_score]
        if not selected and contexts:
            selected = [scored[0][1]]
        for ctx in selected:
            ctx.relevance_score = round(ctx.relevance_score + 0.1, 4)
        return selected[: self.cfg.plan_top_k]
