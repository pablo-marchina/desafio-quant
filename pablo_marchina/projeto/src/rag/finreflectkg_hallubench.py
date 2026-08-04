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


_FINANCIAL_PROMPT = """Does this financial text contain hallucinations or unsupported claims?
Return ONLY: HALLUCINATION or ACCURATE.

Text: {text}
Answer:"""
_FINANCIAL_TERMS = {
    "revenue",
    "profit",
    "margin",
    "growth",
    "valuation",
    "funding",
    "series",
    "acquisition",
    "ipo",
    "ebitda",
}


class FinreflectkgHallubench:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._nvidia = _get_nvidia()

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            for ctx in contexts:
                if not self._is_financial(ctx.content):
                    continue

                    result = self._check_financial_hallucination(ctx.content[:512])

                    if result == "HALLUCINATION":
                        ctx.relevance_score = round(ctx.relevance_score * 0.1, 4)

        return contexts

    def _is_financial(self, text: str) -> bool:
        lower = text.lower()
        return any(t in lower for t in _FINANCIAL_TERMS) or bool(re.search(r"[R\$]?\d+(?:\.\d{3})*(?:,\d{2})?", text))

    def _check_financial_hallucination(self, text: str) -> str | None:
        reply = self._nvidia.llm_generate(_FINANCIAL_PROMPT.format(text=text[:400]), max_tokens=10, temperature=0.01)
        if reply:
            answer = reply.strip().upper()
            if answer in ("HALLUCINATION", "ACCURATE"):
                return answer
        numbers = re.findall(r"\b\d{6,}\b", text)
        return "HALLUCINATION" if len(numbers) > 2 else None
