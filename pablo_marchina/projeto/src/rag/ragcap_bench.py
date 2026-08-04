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


_RAGCAP_PROMPT = """Rate this context's capability to answer a factual question on 0.0-1.0.
Consider: relevance, factual density, completeness.

Context: {context}
Capability score:"""


class RagcapBench:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._nvidia = _get_nvidia()

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            for ctx in contexts:
                score = self._rate_capability(ctx.content[:512])

                if score is not None:
                    ctx.relevance_score = round(0.4 * ctx.relevance_score + 0.6 * score, 4)

        return contexts

    def _rate_capability(self, text: str) -> float | None:
        reply = self._nvidia.llm_generate(_RAGCAP_PROMPT.format(context=text[:400]), max_tokens=10, temperature=0.01)
        if reply:
            try:
                return max(0.0, min(1.0, float(reply.strip().split()[0])))
            except (ValueError, IndexError):
                pass
        sentences = text.count(".")
        numbers = sum(1 for c in text if c.isdigit())
        return round(min(1.0, (sentences * 0.1 + numbers * 0.02)), 4)
