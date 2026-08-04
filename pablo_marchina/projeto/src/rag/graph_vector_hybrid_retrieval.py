"""Graph + vector hybrid retrieval — hybrid graph+vector."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class GraphVectorHybridRetrievalConfig(BaseModel):
    graph_weight: float = 0.4
    vector_weight: float = 0.6


class GraphVectorHybridRetrieval:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = GraphVectorHybridRetrievalConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query = kwargs.get("query", "")
        for ctx in contexts:
            entities = set(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", ctx.content))

            graph_score = min(0.3, len(entities) * 0.02)

            vector_score = ctx.relevance_score

            if query:
                overlap = len(set(query.lower().split()) & set(ctx.content.lower().split()))

                vector_score = overlap / max(1, len(query.split()))

                hybrid = self.cfg.graph_weight * graph_score + self.cfg.vector_weight * vector_score

                ctx.relevance_score = round(min(1.0, hybrid), 4)

        return contexts
