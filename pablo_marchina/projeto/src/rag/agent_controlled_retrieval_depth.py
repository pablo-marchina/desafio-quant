"""Agent-controlled retrieval depth — control retrieval depth."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class AgentControlledRetrievalDepthConfig(BaseModel):
    depth_min: int = 1
    depth_max: int = 5


class AgentControlledRetrievalDepth:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = AgentControlledRetrievalDepthConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts
        depth = min(
            self.cfg.depth_max,
            max(self.cfg.depth_min, int(len(contexts) * 0.5)),
        )
        result = []
        for i, ctx in enumerate(contexts):
            if i < depth:
                ctx.relevance_score = round(min(1.0, ctx.relevance_score * 1.1), 4)
            else:
                ctx.relevance_score = round(ctx.relevance_score * 0.9, 4)
            result.append(ctx)
        return result
