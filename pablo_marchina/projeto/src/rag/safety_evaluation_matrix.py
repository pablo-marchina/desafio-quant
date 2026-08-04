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


_SAFETY_PROMPT = """Does this text contain harmful, unsafe, or prohibited content? Answer ONLY: SAFE or UNSAFE.
Text: {text}
Answer:"""


class SafetyEvaluationMatrix:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._nvidia = _get_nvidia()

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

        for ctx in contexts:
            result = self._check_safety(ctx.content[:512])

            if result == "UNSAFE":
                ctx.relevance_score = round(ctx.relevance_score * 0.05, 4)

            elif result == "SAFE":
                ctx.relevance_score = round(ctx.relevance_score * 1.1, 4)

        return contexts

    def _check_safety(self, text: str) -> str | None:
        reply = self._nvidia.llm_generate(_SAFETY_PROMPT.format(text=text[:400]), max_tokens=10, temperature=0.01)
        if reply:
            answer = reply.strip().upper()
            if answer in ("SAFE", "UNSAFE"):
                return answer
        harmful = {"violence", "hate", "discrimination", "illegal", "malware", "exploit", "harm"}
        lower = text.lower()
        return "UNSAFE" if any(w in lower for w in harmful) else "SAFE"
