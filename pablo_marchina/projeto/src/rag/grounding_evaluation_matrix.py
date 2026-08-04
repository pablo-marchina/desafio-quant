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


_GROUNDING_PROMPT = """Rate how well this text is grounded in evidence on 0.0-1.0.
0.0 = no evidence, speculative
1.0 = fully evidence-based

Text: {text}
Groundedness:"""


class GroundingEvaluationMatrix:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._nvidia = _get_nvidia()

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            for ctx in contexts:
                score = self._score_grounding(ctx.content[:512])

                if score is not None:
                    ctx.relevance_score = round(0.3 * ctx.relevance_score + 0.7 * score, 4)

        return contexts

    def _score_grounding(self, text: str) -> float | None:
        reply = self._nvidia.llm_generate(_GROUNDING_PROMPT.format(text=text[:400]), max_tokens=10, temperature=0.01)
        if reply:
            try:
                return max(0.0, min(1.0, float(reply.strip().split()[0])))
            except (ValueError, IndexError):
                pass
        has_url = "http" in text.lower()
        has_numbers = any(c.isdigit() for c in text)
        has_quotes = '"' in text or "'" in text
        score = 0.3
        if has_url:
            score += 0.4
        if has_numbers:
            score += 0.15
        if has_quotes:
            score += 0.15
        return round(min(1.0, score), 4)
