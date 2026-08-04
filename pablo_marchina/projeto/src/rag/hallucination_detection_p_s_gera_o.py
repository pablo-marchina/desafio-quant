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


_HALLUC_PROMPT = """Is the following statement likely hallucinated (not supported by real facts)?
Answer ONLY: YES, NO, or UNCLEAR.

Statement: {statement}
Answer:"""


class HallucinationDetectionPSGeraO:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._nvidia = _get_nvidia()

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            for ctx in contexts:
                is_hallucination = self._detect_hallucination(ctx.content[:256])

                if is_hallucination:
                    ctx.relevance_score = round(ctx.relevance_score * 0.2, 4)

        return contexts

    def _detect_hallucination(self, text: str) -> bool:
        reply = self._nvidia.llm_generate(_HALLUC_PROMPT.format(statement=text[:200]), max_tokens=10, temperature=0.01)
        if reply:
            return reply.strip().upper() == "YES"
        vague_words = {"may", "might", "could", "possibly", "perhaps", "maybe", "seems", "appears"}
        words = set(text.lower().split())
        return len(words & vague_words) >= 2
