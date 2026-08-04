from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class MultiHopGraphTraverser:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._traversal_graph: dict[str, set[str]] = {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        max_hops = self.config.get("max_hops", 3)
        for ctx in contexts:
            tokens = set(ctx.content.lower().split())

            neighbors: set[str] = set()

            for other in contexts:
                if other.chunk_id == ctx.chunk_id:
                    continue

                    other_tokens = set(other.content.lower().split())

                    overlap = len(tokens & other_tokens)

                    if overlap >= 3:
                        neighbors.add(other.chunk_id)

                        self._traversal_graph[ctx.chunk_id] = neighbors

                        hop_score = min(len(neighbors) / max(len(contexts), 1) * max_hops, 1.0)

                        ctx.relevance_score = round(min(1.0, ctx.relevance_score + hop_score * 0.1), 4)

        return contexts
