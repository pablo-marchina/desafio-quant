from __future__ import annotations

import time
from typing import Any

from src.rag.nvidia_client import NvidiaClient
from src.rag.schemas import RetrievedContext

_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


_MONITOR_PROMPT = """Does the following text contain hallucinated or unsubstantiated claims? Answer ONLY: HALLUCINATION or OK.
Text: {text}
Answer:"""


class RealTimeHallucinationMonitor:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._nvidia = _get_nvidia()
        self._last_check: dict[str, float] = {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            for ctx in contexts:
                now = time.time()

                if ctx.chunk_id in self._last_check and now - self._last_check[ctx.chunk_id] < 60.0:
                    continue

                    self._last_check[ctx.chunk_id] = now

                    result = self._monitor(ctx.content[:256])

                    if result == "HALLUCINATION":
                        ctx.relevance_score = round(ctx.relevance_score * 0.1, 4)

        return contexts

    def _monitor(self, text: str) -> str | None:
        reply = self._nvidia.llm_generate(_MONITOR_PROMPT.format(text=text[:200]), max_tokens=10, temperature=0.01)
        if reply:
            answer = reply.strip().upper()
            if answer in ("HALLUCINATION", "OK"):
                return answer
        return None
