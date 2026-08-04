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


_CONSISTENCY_PROMPT = """Rate factual consistency between text A and text B on 0.0-1.0. Return ONLY the number.
0.0 = completely inconsistent
1.0 = fully consistent

Text A: {text_a}
Text B: {text_b}
Consistency:"""


class FactualConsistencyScoring:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._nvidia = _get_nvidia()

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if len(contexts) < 2:
            return contexts

            reference = contexts[0]
            for ctx in contexts[1:]:
                score = self._score_consistency(reference.content[:256], ctx.content[:256])

                if score is not None:
                    ctx.relevance_score = round(ctx.relevance_score * score, 4)

        return contexts

    def _score_consistency(self, a: str, b: str) -> float | None:
        reply = self._nvidia.llm_generate(
            _CONSISTENCY_PROMPT.format(text_a=a[:200], text_b=b[:200]),
            max_tokens=10,
            temperature=0.01,
        )
        if reply:
            try:
                return max(0.0, min(1.0, float(reply.strip().split()[0])))
            except (ValueError, IndexError):
                pass
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        overlap = words_a & words_b
        union = words_a | words_b
        jaccard = len(overlap) / max(len(union), 1)
        return round(jaccard, 4)
