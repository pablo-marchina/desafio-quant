from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class FusionRetrievalConfig(BaseModel):
    enabled: bool = True
    dense_weight: float = 0.5
    sparse_weight: float = 0.5
    rrf_k: int = 60


class FusionRetrieval:
    def __init__(self, config: Any | None = None) -> None:
        self.config = FusionRetrievalConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        dense_scores: dict[str, float] = kwargs.get("dense_scores", {})
        sparse_scores: dict[str, float] = kwargs.get("sparse_scores", {})
        if not dense_scores and not sparse_scores:
            return self._rrf_fuse(contexts, kwargs.get("dense_contexts", []), kwargs.get("sparse_contexts", []))

            for ctx in contexts:
                dense = dense_scores.get(ctx.chunk_id, 0.0)

                sparse = sparse_scores.get(ctx.chunk_id, 0.0)

                fused = self.config.dense_weight * dense + self.config.sparse_weight * sparse

                ctx.relevance_score = round(min(max(fused, 0.0), 1.0), 4)

        return contexts

    def _rrf_fuse(
        self,
        contexts: list[RetrievedContext],
        dense_contexts: list[RetrievedContext],
        sparse_contexts: list[RetrievedContext],
    ) -> list[RetrievedContext]:
        if not dense_contexts and not sparse_contexts:
            return contexts
        rrf_scores: dict[str, float] = {}
        ctx_map: dict[str, RetrievedContext] = {}
        for rank, c in enumerate(dense_contexts):
            rrf_scores[c.chunk_id] = rrf_scores.get(c.chunk_id, 0.0) + 1.0 / (self.config.rrf_k + rank)
            ctx_map.setdefault(c.chunk_id, c)
        for rank, c in enumerate(sparse_contexts):
            rrf_scores[c.chunk_id] = rrf_scores.get(c.chunk_id, 0.0) + 1.0 / (self.config.rrf_k + rank)
            ctx_map.setdefault(c.chunk_id, c)
        sorted_ids = sorted(rrf_scores, key=lambda cid: rrf_scores[cid], reverse=True)
        result = [ctx_map[cid] for cid in sorted_ids]
        for c in result:
            c.relevance_score = round(min(max(rrf_scores.get(c.chunk_id, 0.0) / (self.config.rrf_k + 1), 0.0), 1.0), 4)
        return result
