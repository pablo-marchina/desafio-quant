from __future__ import annotations

import re
from typing import Any

from src.rag.nvidia_client import NvidiaClient
from src.rag.schemas import RetrievedContext

_TOXIC_PATTERNS = [
    r"\b(kill|die|destroy|attack|hack|bomb|weapon)\b",
    r"\b(hate|racist|fascist|nazi|terrorist)\b",
    r"\b(suicide|self-harm|self.harm)\b",
    r"\b(dox|doxx|swat|swatting)\b",
]

_BIAS_KEYWORDS = [
    "all [group] are",
    "always [group]",
    "never [group]",
    "inferior",
    "superior race",
    "genocide",
    "ethnic cleansing",
]

_SAFETY_TOPICS = [
    "how to make",
    "instructions for",
    "step by step guide to",
    "illegal",
    "unlawful",
    "exploit",
    "vulnerability",
]


class NvidiaNemoGuardrails:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._nvidia = NvidiaClient()
        self._toxicity_re = [re.compile(p, re.IGNORECASE) for p in _TOXIC_PATTERNS]
        self._use_llm = bool(self.config.get("use_llm", False))

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            flags = self._check(ctx.content)

            if flags:
                safety_penalty = len(flags) * 0.15

                ctx.relevance_score = round(max(0.0, ctx.relevance_score - safety_penalty), 4)

        return contexts

    def _check(self, content: str) -> list[str]:
        content_lower = content.lower()
        flags: list[str] = []
        for regex in self._toxicity_re:
            if regex.search(content):
                flags.append("toxicity")
                break
        for kw in _BIAS_KEYWORDS:
            if kw in content_lower:
                flags.append("bias")
                break
        for st in _SAFETY_TOPICS:
            if st in content_lower:
                flags.append("unsafe_topic")
                break
        if self._use_llm and len(flags) == 0:
            result = self._nvidia.llm_generate(
                f"Does the following text contain harmful content? Answer YES or NO only.\n\n{content[:2000]}"
            )
            if result and result.strip().upper().startswith("YES"):
                flags.append("llm_harmful")
        return flags
