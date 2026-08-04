from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class QueryTypeErrorSlices:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

        query = str(kwargs.get("query", "")).lower()
        if not query:
            return contexts

        q_type = self._classify_query(query)
        if q_type == "factoid":
            factor = 1.2
        elif q_type == "explanatory":
            factor = 1.0
        elif q_type == "comparative":
            factor = 1.15
        else:
            factor = 0.9

        for ctx in contexts:
            ctx.relevance_score = round(ctx.relevance_score * factor, 4)

        return contexts

    @staticmethod
    def _classify_query(query: str) -> str:
        if any(w in query for w in ["what is", "what are", "who is", "when", "where", "how many", "how much"]):
            return "factoid"
        if any(w in query for w in ["how does", "why", "explain", "describe", "what is the difference"]):
            return "explanatory"
        if any(w in query for w in ["compare", "vs", "versus", "better", "difference between"]):
            return "comparative"
        return "general"
