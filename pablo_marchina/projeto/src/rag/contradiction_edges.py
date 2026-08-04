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


_CONTRADICT_PROMPT = """Do the following two texts contradict each other? Answer ONLY: YES, NO, or UNCLEAR.

Text A: {text_a}
Text B: {text_b}
Answer:"""


class ContradictionEdges:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._nvidia = _get_nvidia()

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if len(contexts) < 2:
            return contexts

            contradiction_ids: set[str] = set()
            for i in range(len(contexts)):
                for j in range(i + 1, len(contexts)):
                    if self._check_contradiction(contexts[i].content[:256], contexts[j].content[:256]):
                        contradiction_ids.add(contexts[i].chunk_id)

                        contradiction_ids.add(contexts[j].chunk_id)

                        for ctx in contexts:
                            if ctx.chunk_id in contradiction_ids:
                                ctx.relevance_score = round(ctx.relevance_score * 0.7, 4)

        return contexts

    def _check_contradiction(self, a: str, b: str) -> bool:
        reply = self._nvidia.llm_generate(
            _CONTRADICT_PROMPT.format(text_a=a[:200], text_b=b[:200]),
            max_tokens=10,
            temperature=0.01,
        )
        if reply:
            answer = reply.strip().upper()
            return answer == "YES"
        return self._keyword_contradiction(a, b)

    @staticmethod
    def _keyword_contradiction(a: str, b: str) -> bool:
        negation_a = any(w in a.lower() for w in ["not", "no", "never", "cannot", "doesn't", "isn't", "aren't"])
        negation_b = any(w in b.lower() for w in ["not", "no", "never", "cannot", "doesn't", "isn't", "aren't"])
        return negation_a != negation_b
