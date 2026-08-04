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


_CONTRADICTED_PROMPT = """Is the following claim contradicted by any known facts? Answer ONLY: YES, NO, or UNCLEAR.
Claim: {claim}
Answer:"""


class ContradictedClaimFlag:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._nvidia = _get_nvidia()

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            for ctx in contexts:
                flag = self._is_contradicted(ctx.content[:256])

                if flag:
                    ctx.relevance_score = round(ctx.relevance_score * 0.3, 4)

        return contexts

    def _is_contradicted(self, text: str) -> bool:
        reply = self._nvidia.llm_generate(
            _CONTRADICTED_PROMPT.format(claim=text[:200]), max_tokens=10, temperature=0.01
        )
        if reply:
            return reply.strip().upper() == "YES"
        negations = ["not", "no", "never", "cannot", "doesn't", "isn't", "aren't", "contradict"]
        return any(w in text.lower() for w in negations)
