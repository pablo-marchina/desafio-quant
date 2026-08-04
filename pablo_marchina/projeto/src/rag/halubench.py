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


_HALU_PROMPT = """Rate this text for hallucination risk on 0.0-1.0:
0.0 = no hallucination risk
1.0 = definite hallucination

Text: {text}
Risk score:"""


class Halubench:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._nvidia = _get_nvidia()

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            for ctx in contexts:
                risk = self._score_hallucination_risk(ctx.content[:512])

                if risk is not None:
                    ctx.relevance_score = round(ctx.relevance_score * (1.0 - risk), 4)

        return contexts

    def _score_hallucination_risk(self, text: str) -> float | None:
        reply = self._nvidia.llm_generate(_HALU_PROMPT.format(text=text[:400]), max_tokens=10, temperature=0.01)
        if reply:
            try:
                return max(0.0, min(1.0, float(reply.strip().split()[0])))
            except (ValueError, IndexError):
                pass
        vague = sum(1 for w in ["may", "might", "could", "perhaps", "maybe"] if w in text.lower().split())
        return round(min(1.0, vague * 0.2), 4)
