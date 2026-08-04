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


_ENTAIL_PROMPT = """Does the premise entail the hypothesis? Answer ONLY: ENTAILMENT, CONTRADICTION, or NEUTRAL.

Premise: {premise}
Hypothesis: {hypothesis}
Answer:"""


class EntailmentBasedVerification:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._nvidia = _get_nvidia()

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if len(contexts) < 2:
            return contexts

        premise = contexts[0].content[:512]
        for ctx in contexts[1:]:
            result = self._check_entailment(premise, ctx.content[:256])

            if result == "ENTAILMENT":
                ctx.relevance_score = round(ctx.relevance_score * 1.3, 4)

            elif result == "CONTRADICTION":
                ctx.relevance_score = round(ctx.relevance_score * 0.3, 4)

        return contexts

    def _check_entailment(self, premise: str, hypothesis: str) -> str | None:
        reply = self._nvidia.llm_generate(
            _ENTAIL_PROMPT.format(premise=premise[:200], hypothesis=hypothesis[:200]),
            max_tokens=10,
            temperature=0.01,
        )
        if reply:
            answer = reply.strip().upper()
            if answer in ("ENTAILMENT", "CONTRADICTION", "NEUTRAL"):
                return answer
        return None
