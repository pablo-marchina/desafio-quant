from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ExplainableRecommendationGraph:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._graph: dict[str, list[dict[str, Any]]] = {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        min_overlap = self.config.get("min_overlap", 3)
        for ctx in contexts:
            ctx_tokens = set(ctx.content.lower().split())

            links: list[dict[str, Any]] = []

            for other in contexts:
                if other.chunk_id == ctx.chunk_id:
                    continue

                    other_tokens = set(other.content.lower().split())

                    overlap = len(ctx_tokens & other_tokens)

                    if overlap >= min_overlap:
                        links.append({"target": other.chunk_id, "overlap": overlap, "score": other.relevance_score})

                        links.sort(key=lambda x: x["overlap"], reverse=True)

                        self._graph[ctx.chunk_id] = links[:5]

        return contexts
