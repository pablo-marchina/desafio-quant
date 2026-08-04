from __future__ import annotations

import re
from typing import Any

from src.rag.nvidia_client import NvidiaClient
from src.rag.schemas import RetrievedContext

_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


_RELEVANCE_PROMPT = """Rate claim relevance to the query on 0.0-1.0. Return ONLY the number.
Query: {query}
Claim: {claim}
Relevance:"""


class ClaimLevelRetrieval:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._nvidia = _get_nvidia()

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

        query_text = str(kwargs.get("query", ""))
        if not query_text:
            return contexts

        for ctx in contexts:
            sentences = re.split(r"(?<=[.!?])\s+", ctx.content[:1024])

            best_score = 0.0

            for sent in sentences[:5]:
                s = sent.strip()

                if len(s) > 15:
                    score = self._rate_relevance(query_text, s)

                    if score is not None and score > best_score:
                        best_score = score

                        if best_score > 0:
                            ctx.relevance_score = round(0.5 * ctx.relevance_score + 0.5 * best_score, 4)

        return contexts

    def _rate_relevance(self, query: str, claim: str) -> float | None:
        reply = self._nvidia.llm_generate(
            _RELEVANCE_PROMPT.format(query=query[:200], claim=claim[:200]),
            max_tokens=10,
            temperature=0.01,
        )
        if reply:
            try:
                return max(0.0, min(1.0, float(reply.strip().split()[0])))
            except (ValueError, IndexError):
                pass
        overlap = len(set(query.lower().split()) & set(claim.lower().split()))
        return round(min(1.0, overlap / 5.0), 4)
