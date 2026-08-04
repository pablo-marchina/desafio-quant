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


_TRIAD_PROMPT = """Rate the quality of this retrieved context on three dimensions (0.0-1.0 each).
Return: relevance=X groundedness=X answer_relevance=X

Context: {context}
Query: {query}
Rating:"""


class RagTriad:
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
                    scores = self._evaluate_triad(query, ctx.content[:512])

                    if scores:
                        avg = sum(scores.values()) / len(scores)

                        ctx.relevance_score = round(avg, 4)

        return contexts

    def _evaluate_triad(self, query: str, context: str) -> dict[str, float] | None:
        reply = self._nvidia.llm_generate(
            _TRIAD_PROMPT.format(context=context[:400], query=query[:200]),
            max_tokens=32,
            temperature=0.01,
        )
        if reply:
            scores: dict[str, float] = {}
            for part in reply.split():
                if "=" in part:
                    key, val = part.split("=", 1)
                    try:
                        scores[key.strip()] = max(0.0, min(1.0, float(val)))
                    except (ValueError, IndexError):
                        pass
            if len(scores) == 3:
                return scores
        overlap = len(set(query.lower().split()) & set(context.lower().split()))
        rel = min(1.0, overlap / 5.0)
        return {"relevance": rel, "groundedness": 0.5, "answer_relevance": rel}
