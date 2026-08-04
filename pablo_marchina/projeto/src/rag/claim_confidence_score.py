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


_CONFIDENCE_PROMPT = """Rate your confidence in the factual accuracy of the following text.
Return ONLY a number between 0.0 and 1.0:
0.0 = completely uncertain / speculative
1.0 = highly certain / well-supported

Text: {text}
Confidence:"""


class ClaimConfidenceScore:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._nvidia = _get_nvidia()

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            for ctx in contexts:
                score = self._score_confidence(ctx.content[:512])

                if score is not None:
                    ctx.relevance_score = round(ctx.relevance_score * score, 4)

        return contexts

    def _score_confidence(self, text: str) -> float | None:
        reply = self._nvidia.llm_generate(_CONFIDENCE_PROMPT.format(text=text[:400]), max_tokens=10, temperature=0.01)
        if reply:
            try:
                return max(0.0, min(1.0, float(reply.strip().split()[0])))
            except (ValueError, IndexError):
                pass
        return self._heuristic_confidence(text)

    @staticmethod
    def _heuristic_confidence(text: str) -> float:
        uncertainty_words = {"maybe", "possibly", "might", "could", "unclear", "unknown", "speculative", "allegedly"}
        certainty_words = {"confirmed", "demonstrated", "proven", "established", "validated", "verified", "official"}
        words = set(text.lower().split())
        uncertainty = len(words & uncertainty_words)
        certainty = len(words & certainty_words)
        ratio = 0.5
        if certainty + uncertainty > 0:
            ratio = certainty / (certainty + uncertainty)
        return round(max(0.1, min(1.0, 0.3 + 0.7 * ratio)), 4)
