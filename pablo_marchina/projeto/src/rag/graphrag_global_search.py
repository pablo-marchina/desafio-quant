"""GraphRAG global search — global graph search across all contexts."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class GraphragGlobalSearchConfig(BaseModel):
    top_global: int = 5


class GraphragGlobalSearch:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = GraphragGlobalSearchConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query = kwargs.get("query", "")
        if not contexts:
            return contexts
        all_entities: list[str] = []
        for ctx in contexts:
            all_entities.extend(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", ctx.content))
        entity_freq = Counter(all_entities)
        top_entities = {e for e, _ in entity_freq.most_common(self.cfg.top_global)}
        for ctx in contexts:
            ctx_entities = set(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", ctx.content))
            global_relevance = len(ctx_entities & top_entities) / max(1, len(top_entities))
            if query:
                global_relevance += sum(1 for w in query.lower().split() if w in ctx.content.lower()) / max(
                    1, len(query.split())
                )
            ctx.relevance_score = round(min(1.0, 0.6 * ctx.relevance_score + 0.4 * global_relevance), 4)
        contexts.sort(key=lambda c: c.relevance_score, reverse=True)
        return contexts[: max(1, self.cfg.top_global)]
