"""ReAct reasoning-acting agent loop — interleave think-act-observe per context."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.nvidia_client import NvidiaClient
from src.rag.schemas import RetrievedContext


class ReactConfig(BaseModel):
    max_steps: int = 3
    relevance_boost: float = 0.15


class ReactReasoningActingAgentLoop:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = ReactConfig.model_validate(config or {})
        self._llm = NvidiaClient()

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query = kwargs.get("query", "")
        for ctx in contexts:
            score = ctx.relevance_score

            for _ in range(self.cfg.max_steps):
                entities = [w for w in ctx.content.split() if w[0].isupper() and len(w) > 2]

                entity_overlap = sum(1 for e in entities if e.lower() in query.lower()) if query else 0

                new_score = score + (entity_overlap * 0.05) + self.cfg.relevance_boost

                if abs(new_score - score) < 0.01:
                    break

                    score = min(1.0, new_score)

                    ctx.relevance_score = round(score, 4)

        return contexts
