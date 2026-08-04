"""Agentic retrieval planner — plan retrieval actions."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class AgenticRetrievalPlannerConfig(BaseModel):
    max_actions: int = 3


class AgenticRetrievalPlanner:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = AgenticRetrievalPlannerConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _plan_action(self, ctx: RetrievedContext) -> tuple[str, float]:
        if not ctx.url:
            return ("locate_source", 0.1)
        if ctx.relevance_score < 0.5:
            return ("re_retrieve", 0.2)
        if len(ctx.gap_types) > 2:
            return ("decompose", 0.15)
        return ("use_as_is", 0.0)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            action, boost = self._plan_action(ctx)

            ctx.relevance_score = round(min(1.0, ctx.relevance_score + boost), 4)

        return contexts
