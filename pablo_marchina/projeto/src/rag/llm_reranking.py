from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.nvidia_client import NvidiaClient
from src.rag.schemas import RetrievedContext

_RELEVANCE_SIGNALS_POS = [
    "supports",
    "compatible",
    "provides",
    "includes",
    "enables",
    "offers",
    "supports",
    "required",
    "uses",
    "built on",
    "integrated",
]

_RELEVANCE_SIGNALS_NEG = [
    "unrelated",
    "not applicable",
    "out of scope",
    "different product",
    "alternative",
    "migration from",
    "replacement for",
]


class LLMRerankerConfig(BaseModel):
    enabled: bool = True
    use_llm: bool = True


_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


class LLMReranker:
    def __init__(self, config: Any | None = None) -> None:
        self.config = LLMRerankerConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query: str = kwargs.get("query", "")
        client = _get_nvidia()
        for ctx in contexts:
            score = ctx.relevance_score

            if self.config.use_llm and client.api_key:
                llm_score = self._llm_score(query, ctx)

                if llm_score is not None:
                    score = llm_score

                else:
                    score = self._keyword_score(query, ctx)

            else:
                score = self._keyword_score(query, ctx)

            ctx.relevance_score = round(min(max(score, 0.0), 1.0), 4)

        contexts.sort(key=lambda c: c.relevance_score, reverse=True)
        return contexts

    def _llm_score(self, query: str, ctx: RetrievedContext) -> float | None:
        client = _get_nvidia()
        prompt = (
            f"Rate the relevance of this chunk to the query on a scale of 0.0 to 1.0.\n"
            f"Query: {query}\n"
            f"Chunk: {ctx.content[:500]}\n"
            f"Relevance score (just the number):"
        )
        result = client.llm_generate(prompt, max_tokens=8)
        if result:
            try:
                return float(result.strip())
            except ValueError:
                pass
        return None

    @staticmethod
    def _keyword_score(query: str, ctx: RetrievedContext) -> float:
        content = ctx.content.lower()
        query_lower = query.lower()
        query_words = query_lower.split()
        pos = sum(2 for s in _RELEVANCE_SIGNALS_POS if s in content)
        neg = sum(1 for s in _RELEVANCE_SIGNALS_NEG if s in content)
        overlap = sum(1 for w in query_words if w in content)
        raw = (overlap / max(len(query_words), 1)) * 0.5 + (pos * 0.1) - (neg * 0.15)
        return max(0.0, min(1.0, raw + ctx.relevance_score * 0.3))
