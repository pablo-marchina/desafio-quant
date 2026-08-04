from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from src.rag.nvidia_client import NvidiaClient
from src.rag.schemas import RetrievedContext

QueryType = Literal["factual", "analytical", "comparative"]

_QUERY_SIGNALS: dict[QueryType, list[str]] = {
    "factual": ["what is", "what are", "when did", "where is", "who is", "how many", "definition", "define"],
    "analytical": ["why", "how does", "explain", "analyze", "what causes", "what factors", "impact", "effect"],
    "comparative": ["vs", "versus", "compare", "difference", "better", "worse", "pros and cons", "tradeoff"],
}


class AdaptiveRAGConfig(BaseModel):
    enabled: bool = True
    llm_fallback_to_keywords: bool = True
    factual_boost: float = 0.1
    analytical_boost: float = 0.05
    comparative_boost: float = 0.15


_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


class AdaptiveRAG:
    def __init__(self, config: Any | None = None) -> None:
        self.config = AdaptiveRAGConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query = kwargs.get("query", "")
        query_type = self._classify_query(query)
        return self._apply(contexts, query_type=query_type, **kwargs)

    def _classify_query(self, query: str) -> QueryType:
        client = _get_nvidia()
        if self.config.llm_fallback_to_keywords:
            llm_result = client.llm_generate(
                f"Classify the query as factual, analytical, or comparative. Query: {query}\nAnswer with one word only."
            )
            if llm_result and llm_result.strip().lower() in {"factual", "analytical", "comparative"}:
                return llm_result.strip().lower()  # type: ignore[return-value]
        q_lower = query.lower()
        for qtype, signals in _QUERY_SIGNALS.items():
            if any(signal in q_lower for signal in signals):
                return qtype
        return "factual"

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query_type: QueryType = kwargs.get("query_type", "factual")
        boost = {
            "factual": self.config.factual_boost,
            "analytical": self.config.analytical_boost,
            "comparative": self.config.comparative_boost,
        }[query_type]
        for ctx in contexts:
            ctx.relevance_score = round(min(ctx.relevance_score + boost, 1.0), 4)

            if query_type == "comparative":
                contexts.sort(key=lambda c: c.relevance_score, reverse=True)

        return contexts
