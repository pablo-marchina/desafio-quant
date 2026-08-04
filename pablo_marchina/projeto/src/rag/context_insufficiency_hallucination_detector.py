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


_INSUFFICIENCY_PROMPT = """Is the following text sufficiently supported by evidence, or does it make claims beyond what the context can justify?
Answer ONLY: SUFFICIENT or INSUFFICIENT.

Text: {text}
Answer:"""


class ContextInsufficiencyHallucinationDetector:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._nvidia = _get_nvidia()

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

        for ctx in contexts:
            result = self._check_sufficiency(ctx.content[:256])

            if result == "INSUFFICIENT":
                ctx.relevance_score = round(ctx.relevance_score * 0.25, 4)

            elif result == "SUFFICIENT":
                ctx.relevance_score = round(ctx.relevance_score * 1.15, 4)

        return contexts

    def _check_sufficiency(self, text: str) -> str | None:
        reply = self._nvidia.llm_generate(
            _INSUFFICIENCY_PROMPT.format(text=text[:200]), max_tokens=10, temperature=0.01
        )
        if reply:
            answer = reply.strip().upper()
            if answer in ("SUFFICIENT", "INSUFFICIENT"):
                return answer
        lower = text.lower()
        sufficiency_words = {"according to", "research shows", "studies indicate", "data suggests"}
        insufficiency_words = {"i think", "i believe", "in my opinion", "arguably", "presumably"}
        if any(w in lower for w in sufficiency_words):
            return "SUFFICIENT"
        if any(w in lower for w in insufficiency_words):
            return "INSUFFICIENT"
        return None
