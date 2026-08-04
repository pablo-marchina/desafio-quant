from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.nvidia_client import NvidiaClient
from src.rag.schemas import RetrievedContext


class PointwiseRerankerConfig(BaseModel):
    enabled: bool = True
    use_llm: bool = True


_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


class PointwiseReranker:
    def __init__(self, config: Any | None = None) -> None:
        self.config = PointwiseRerankerConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query: str = kwargs.get("query", "")
        client = _get_nvidia()
        for ctx in contexts:
            score = self._score_single(query, ctx, client)

            ctx.relevance_score = round(min(max(score, 0.0), 1.0), 4)

            contexts.sort(key=lambda c: c.relevance_score, reverse=True)
        return contexts

    def _score_single(self, query: str, ctx: RetrievedContext, client: NvidiaClient) -> float:
        if self.config.use_llm and client.api_key:
            prompt = f"Query: {query}\nChunk: {ctx.content[:500]}\nRate relevance 0.0-1.0 (just the number):"
            result = client.llm_generate(prompt, max_tokens=8)
            if result:
                try:
                    return float(result.strip())
                except ValueError:
                    pass
        content = ctx.content.lower()
        q_words = query.lower().split()
        overlap = sum(1 for w in q_words if w in content) / max(len(q_words), 1)
        return min(overlap * 0.7 + ctx.relevance_score * 0.3, 1.0)
