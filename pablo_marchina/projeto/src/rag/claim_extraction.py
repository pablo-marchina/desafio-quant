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


_EXTRACT_PROMPT = """Extract all verifiable claims from the text below. Return each claim on a separate line.
Only include factual statements that can be verified or refuted.

Text: {text}"""


class ClaimExtraction:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._nvidia = _get_nvidia()

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            for ctx in contexts:
                claims = self._extract(ctx.content[:1024])

                if claims:
                    ctx.relevance_score = round(ctx.relevance_score + 0.05 * len(claims), 4)

        return contexts

    def _extract(self, text: str) -> list[str]:
        reply = self._nvidia.llm_generate(_EXTRACT_PROMPT.format(text=text[:800]), max_tokens=256, temperature=0.01)
        if reply:
            return [line.strip() for line in reply.split("\n") if line.strip() and len(line.strip()) > 10]
        return self._fallback_extract(text)

    @staticmethod
    def _fallback_extract(text: str) -> list[str]:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        claims: list[str] = []
        for s in sentences:
            s = s.strip()
            if s and len(s) > 15 and not s.startswith(("What", "How", "Why", "Can", "Is", "Are", "Do")):
                claims.append(s)
        return claims[:8]
