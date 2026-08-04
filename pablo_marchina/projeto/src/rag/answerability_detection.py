from __future__ import annotations

from typing import Any

from src.rag.nvidia_client import NvidiaClient
from src.rag.schemas import RetrievedContext

_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


_ANSWERABLE_PROMPT = """Can this context answer the query? Return ONLY: YES or NO.
Query: {query}
Context: {context}
Answer:"""


class AnswerabilityDetection:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._nvidia = _get_nvidia()

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

        query = str(kwargs.get("query", ""))
        if not query:
            return contexts

        for ctx in contexts:
            result = self._check_answerable(query, ctx.content[:256])

            if result == "NO":
                ctx.relevance_score = round(ctx.relevance_score * 0.3, 4)

            elif result == "YES":
                ctx.relevance_score = round(ctx.relevance_score * 1.2, 4)

        return contexts

    def _check_answerable(self, query: str, context: str) -> str | None:
        reply = self._nvidia.llm_generate(
            _ANSWERABLE_PROMPT.format(query=query[:200], context=context[:200]),
            max_tokens=10,
            temperature=0.01,
        )
        if reply:
            answer = reply.strip().upper()
            if answer in ("YES", "NO"):
                return answer
        query_terms = set(query.lower().split())
        context_terms = set(context.lower().split())
        overlap = query_terms & context_terms
        return "YES" if len(overlap) >= 2 else "NO"
