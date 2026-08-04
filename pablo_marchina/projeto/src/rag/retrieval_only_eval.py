from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RetrievalOnlyEval:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            query = str(kwargs.get("query", "")).lower()
            query_terms = set(query.split())
            for ctx in contexts:
                if not query_terms:
                    continue

                    content_lower = ctx.content.lower()

                    match_count = sum(1 for t in query_terms if t in content_lower)

                    recall = match_count / max(len(query_terms), 1)

                    ctx.relevance_score = round(ctx.relevance_score * (0.5 + 0.5 * recall), 4)

        return contexts
