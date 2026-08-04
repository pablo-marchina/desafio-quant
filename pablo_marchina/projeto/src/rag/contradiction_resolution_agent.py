"""Contradiction resolution agent — resolve contradictions across contexts."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class ContradictionResolutionAgentConfig(BaseModel):
    contradiction_penalty: float = 0.15


class ContradictionResolutionAgent:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = ContradictionResolutionAgentConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        entity_claims: defaultdict[str, list[RetrievedContext]] = defaultdict(list)
        for ctx in contexts:
            entities = [w for w in ctx.content.split() if w[0].isupper() and len(w) > 2]

            for e in set(entities):
                entity_claims[e].append(ctx)

        contradiction_count: defaultdict[str, int] = defaultdict(int)
        for ctxs in entity_claims.values():
            if len(ctxs) > 1:
                scores = [c.relevance_score for c in ctxs]
                if max(scores) - min(scores) > 0.5:
                    for c in ctxs:
                        contradiction_count[c.chunk_id] += 1

        for ctx in contexts:
            penalty = contradiction_count.get(ctx.chunk_id, 0) * self.cfg.contradiction_penalty
            ctx.relevance_score = round(max(0.0, ctx.relevance_score - penalty), 4)

        return contexts
