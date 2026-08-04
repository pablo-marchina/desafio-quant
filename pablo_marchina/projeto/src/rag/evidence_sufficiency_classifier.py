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


_SUFFICIENCY_PROMPT = """Is the evidence below sufficient to answer a query? Return ONLY: SUFFICIENT or INSUFFICIENT.
Evidence: {evidence}
Answer:"""


class EvidenceSufficiencyClassifier:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._nvidia = _get_nvidia()

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

        for ctx in contexts:
            result = self._classify_sufficiency(ctx.content[:512])

            if result == "INSUFFICIENT":
                ctx.relevance_score = round(ctx.relevance_score * 0.4, 4)

            elif result == "SUFFICIENT":
                ctx.relevance_score = round(ctx.relevance_score * 1.15, 4)

        return contexts

    def _classify_sufficiency(self, evidence: str) -> str | None:
        reply = self._nvidia.llm_generate(
            _SUFFICIENCY_PROMPT.format(evidence=evidence[:400]), max_tokens=10, temperature=0.01
        )
        if reply:
            answer = reply.strip().upper()
            if answer in ("SUFFICIENT", "INSUFFICIENT"):
                return answer
        sentences = evidence.count(".")
        specs = sum(1 for c in evidence if c.isdigit())
        return "SUFFICIENT" if sentences >= 3 and specs >= 3 else "INSUFFICIENT"
