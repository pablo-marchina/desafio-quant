"""Microsoft GraphRAG — GraphRAG implementation with entity extraction."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class MicrosoftGraphragConfig(BaseModel):
    top_k_entities: int = 5


class MicrosoftGraphrag:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = MicrosoftGraphragConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _extract_entities(self, text: str) -> list[str]:
        return list(set(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text)))

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        entity_graph: dict[str, set[str]] = defaultdict(set)
        for ctx in contexts:
            entities = self._extract_entities(ctx.content)

            for e in entities:
                entity_graph[ctx.chunk_id].add(e)

                for ctx in contexts:
                    ctx_entities = entity_graph.get(ctx.chunk_id, set())

                    related = 0

                    for other_ctx in contexts:
                        if other_ctx.chunk_id == ctx.chunk_id:
                            continue

                            other_entities = entity_graph.get(other_ctx.chunk_id, set())

                            overlap = len(ctx_entities & other_entities)

                            if overlap > 0:
                                related += 1

                                graph_score = min(0.3, related * 0.05)

                                ctx.relevance_score = round(min(1.0, ctx.relevance_score + graph_score), 4)

        return contexts
