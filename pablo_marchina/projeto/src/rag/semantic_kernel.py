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


_SK_PROMPT = """Rate this context for Semantic Kernel planning on 0.0-1.0.
Consider: actionability, clarity, specificity.

Context: {context}
Planning value:"""


class SemanticKernel:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._nvidia = _get_nvidia()

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            for ctx in contexts:
                score = self._semantic_score(ctx.content[:512])

                if score is not None:
                    ctx.relevance_score = round(0.4 * ctx.relevance_score + 0.6 * score, 4)

        return contexts

    def _semantic_score(self, text: str) -> float | None:
        reply = self._nvidia.llm_generate(_SK_PROMPT.format(context=text[:400]), max_tokens=10, temperature=0.01)
        if reply:
            try:
                return max(0.0, min(1.0, float(reply.strip().split()[0])))
            except (ValueError, IndexError):
                pass
        action_words = {"use", "build", "create", "deploy", "configure", "run", "install", "setup", "implement"}
        lower = set(text.lower().split())
        return round(min(1.0, len(lower & action_words) * 0.15), 4)
