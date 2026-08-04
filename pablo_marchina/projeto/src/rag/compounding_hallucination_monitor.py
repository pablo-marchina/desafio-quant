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


_COMPOUND_PROMPT = """Does this text build on a claim that appears unsupported or hallucinated?
Answer ONLY: COMPOUNDING or SAFE.

Text: {text}
Answer:"""


class CompoundingHallucinationMonitor:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._nvidia = _get_nvidia()
        self._hallucination_tracker: dict[str, float] = {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            for ctx in contexts:
                result = self._check_compounding(ctx.content[:256])

                if result == "COMPOUNDING":
                    ctx.relevance_score = round(ctx.relevance_score * 0.15, 4)

                    now = time.time()

                    for chunk_id in list(self._hallucination_tracker.keys()):
                        if now - self._hallucination_tracker[chunk_id] > 300.0:
                            del self._hallucination_tracker[chunk_id]

        return contexts

    def _check_compounding(self, text: str) -> str | None:
        reply = self._nvidia.llm_generate(_COMPOUND_PROMPT.format(text=text[:200]), max_tokens=10, temperature=0.01)
        if reply:
            answer = reply.strip().upper()
            if answer in ("COMPOUNDING", "SAFE"):
                return answer
        hedges = {"therefore", "thus", "consequently", "as a result", "this means", "this implies", "based on"}
        lower = text.lower()
        return "COMPOUNDING" if any(h in lower for h in hedges) else None
