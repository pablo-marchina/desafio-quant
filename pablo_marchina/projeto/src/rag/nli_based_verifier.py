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


_NLI_PROMPT = """Given the context, is the claim TRUE, FALSE, or UNVERIFIABLE? Return ONLY one word.

Context: {context}
Claim: {claim}
Answer:"""


class NliBasedVerifier:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._nvidia = _get_nvidia()

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

        for ctx in contexts:
            sentences = [
                s.strip() for s in ctx.content.replace("?", ".").replace("!", ".").split(".") if len(s.strip()) > 20
            ]

            true_count = 0

            false_count = 0

            for sent in sentences[:5]:
                result = self._verify(sent, ctx.content[:512])

                if result == "TRUE":
                    true_count += 1

                elif result == "FALSE":
                    false_count += 1

                    if true_count > false_count:
                        ctx.relevance_score = round(ctx.relevance_score * 1.2, 4)

                    elif false_count > true_count:
                        ctx.relevance_score = round(ctx.relevance_score * 0.4, 4)

        return contexts

    def _verify(self, claim: str, context: str) -> str | None:
        reply = self._nvidia.llm_generate(
            _NLI_PROMPT.format(context=context[:400], claim=claim[:200]),
            max_tokens=10,
            temperature=0.01,
        )
        if reply:
            answer = reply.strip().upper()
            if answer in ("TRUE", "FALSE", "UNVERIFIABLE"):
                return answer
        return None
