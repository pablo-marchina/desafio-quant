"""RAPTOR hierarchical retrieval — RAPTOR-style retrieval."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class RaptorHierarchicalRetrievalConfig(BaseModel):
    cluster_size: int = 3


class RaptorHierarchicalRetrieval:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = RaptorHierarchicalRetrievalConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts
        scored = sorted(contexts, key=lambda c: c.relevance_score, reverse=True)
        clusters = [scored[i : i + self.cfg.cluster_size] for i in range(0, len(scored), self.cfg.cluster_size)]
        result = []
        for cluster in clusters:
            if not cluster:
                continue
            avg = sum(c.relevance_score for c in cluster) / len(cluster)
            for ctx in cluster:
                ctx.relevance_score = round(min(1.0, avg * 0.7 + ctx.relevance_score * 0.3), 4)
            result.extend(cluster)
        return result
