from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from src.rag.nvidia_client import NvidiaClient
from src.rag.schemas import RetrievedContext

Strategy = Literal["dense", "sparse", "hybrid", "graph", "keyword"]

_STRATEGY_SIGNALS: dict[Strategy, list[str]] = {
    "dense": ["semantic", "meaning", "concept", "related", "similar", "context"],
    "sparse": ["exact", "keyword", "term", "phrase", "specific word", "literal"],
    "hybrid": ["overview", "general", "broad", "comprehensive", "summary"],
    "graph": ["relationship", "connection", "path", "graph", "network", "linked"],
    "keyword": ["find", "search", "look up", "where", "what is the term"],
}


class MetaRetrievalConfig(BaseModel):
    enabled: bool = True
    use_llm: bool = True
    default_strategy: str = "hybrid"


_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


class MetaRetrieval:
    def __init__(self, config: Any | None = None) -> None:
        self.config = MetaRetrievalConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query: str = kwargs.get("query", "")
        strategy = self._select_strategy(query)
        booster = {"dense": 0.1, "sparse": 0.0, "hybrid": 0.05, "graph": 0.15, "keyword": -0.05}
        boost = booster.get(strategy, 0.0)
        for ctx in contexts:
            ctx.relevance_score = round(min(ctx.relevance_score + boost, 1.0), 4)

        return contexts

    def _select_strategy(self, query: str) -> Strategy:
        client = _get_nvidia()
        if self.config.use_llm and client.api_key:
            result = client.llm_generate(
                f"Select the best retrieval strategy for this query: dense, sparse, hybrid, graph, or keyword.\n"
                f"Query: {query}\nAnswer with one word only."
            )
            if result and result.strip().lower() in {"dense", "sparse", "hybrid", "graph", "keyword"}:
                return result.strip().lower()  # type: ignore[return-value]
        q_lower = query.lower()
        best_strategy: Strategy = "hybrid"
        best_count = 0
        for strategy, signals in _STRATEGY_SIGNALS.items():
            count = sum(1 for s in signals if s in q_lower)
            if count > best_count:
                best_count = count
                best_strategy = strategy
        return best_strategy
