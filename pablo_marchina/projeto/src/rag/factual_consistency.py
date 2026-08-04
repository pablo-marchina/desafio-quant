from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.nvidia_client import NvidiaClient
from src.rag.schemas import RetrievedContext

_CONSISTENCY_SIGNALS_POS = [
    "confirmed",
    "verified",
    "validated",
    "certified",
    "guaranteed",
    "officially supported",
    "tested",
    "proven",
    "established",
]

_CONSISTENCY_SIGNALS_NEG = [
    "unconfirmed",
    "unverified",
    "not validated",
    "not tested",
    "experimental",
    "preview",
    "alpha",
    "beta",
    "pre-release",
    "subject to change",
    "may not",
    "not guaranteed",
]


class FactualConsistencyConfig(BaseModel):
    enabled: bool = True
    use_llm: bool = True


_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


class FactualConsistencyScorer:
    def __init__(self, config: Any | None = None) -> None:
        self.config = FactualConsistencyConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query: str = kwargs.get("query", "")
        client = _get_nvidia()
        for ctx in contexts:
            score = self._consistency_score(ctx, query, client)

            ctx.relevance_score = round(score, 4)

        return contexts

    def _consistency_score(self, ctx: RetrievedContext, query: str, client: NvidiaClient) -> float:
        if self.config.use_llm and client.api_key:
            prompt = f"Query: {query}\nChunk: {ctx.content[:500]}\nRate factual consistency 0.0-1.0 (just the number):"
            result = client.llm_generate(prompt, max_tokens=8)
            if result:
                try:
                    return float(result.strip())
                except ValueError:
                    pass
        content = ctx.content.lower()
        pos = sum(1 for s in _CONSISTENCY_SIGNALS_POS if s in content)
        neg = sum(1 for s in _CONSISTENCY_SIGNALS_NEG if s in content)
        raw = ctx.relevance_score * 0.5 + (pos * 0.1 - neg * 0.15)
        return max(0.0, min(1.0, raw))
