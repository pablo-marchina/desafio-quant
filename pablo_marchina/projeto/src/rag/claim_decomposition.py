from __future__ import annotations

import re
from typing import Any

from src.rag.nvidia_client import NvidiaClient
from src.rag.schemas import RetrievedContext

_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


_DECOMPOSE_PROMPT = """Decompose the following text into atomic claims. Return one claim per line, numbered.
Each claim must be a single verifiable statement.

Text: {text}

Atomic claims:"""


class ClaimDecomposition:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._nvidia = _get_nvidia()

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            for ctx in contexts:
                raw = ctx.content[:1024]

                claims = self._decompose(raw)

                if claims:
                    ctx.relevance_score = round(ctx.relevance_score * (1.0 + 0.1 * min(len(claims), 5)), 4)

        return contexts

    def _decompose(self, text: str) -> list[str]:
        reply = self._nvidia.llm_generate(_DECOMPOSE_PROMPT.format(text=text[:800]), max_tokens=256, temperature=0.01)
        if reply:
            return self._parse_claims(reply)
        return self._keyword_decompose(text)

    @staticmethod
    def _parse_claims(reply: str) -> list[str]:
        claims: list[str] = []
        for line in reply.strip().split("\n"):
            cleaned = re.sub(r"^\d+[\.\)]\s*", "", line).strip()
            if cleaned and len(cleaned) > 10:
                claims.append(cleaned)
        return claims

    @staticmethod
    def _keyword_decompose(text: str) -> list[str]:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if len(s.strip()) > 15][:10]
