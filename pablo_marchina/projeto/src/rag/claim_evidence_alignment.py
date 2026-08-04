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


_ALIGN_PROMPT = """On a scale of 0.0 to 1.0, how well does the evidence support the claim?
0.0 = no support at all
1.0 = fully supports

Claim: {claim}
Evidence: {evidence}
Alignment score:"""


class ClaimEvidenceAlignment:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._nvidia = _get_nvidia()

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            for i, ctx in enumerate(contexts):
                if i == 0:
                    continue

                    alignment = self._score_alignment(contexts[0].content[:256], ctx.content[:256])

                    if alignment is not None:
                        ctx.relevance_score = round(ctx.relevance_score * alignment, 4)

        return contexts

    def _score_alignment(self, claim: str, evidence: str) -> float | None:
        reply = self._nvidia.llm_generate(
            _ALIGN_PROMPT.format(claim=claim, evidence=evidence), max_tokens=10, temperature=0.01
        )
        if reply:
            try:
                return max(0.0, min(1.0, float(reply.strip().split()[0])))
            except (ValueError, IndexError):
                pass
        return 0.5
