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


_GEN_MATRIX_PROMPT = """Rate this generation on 0.0-1.0 for: fluency, coherence, completeness.
Return: fluency=X coherence=X completeness=X

Text: {text}
Rating:"""


class GenerationEvaluationMatrix:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._nvidia = _get_nvidia()

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            for ctx in contexts:
                scores = self._evaluate_generation(ctx.content[:512])

                if scores:
                    avg = sum(scores.values()) / len(scores)

                    ctx.relevance_score = round(avg, 4)

        return contexts

    def _evaluate_generation(self, text: str) -> dict[str, float] | None:
        reply = self._nvidia.llm_generate(_GEN_MATRIX_PROMPT.format(text=text[:400]), max_tokens=32, temperature=0.01)
        if reply:
            scores: dict[str, float] = {}
            for part in reply.split():
                if "=" in part:
                    key, val = part.split("=", 1)
                    try:
                        scores[key.strip()] = max(0.0, min(1.0, float(val)))
                    except (ValueError, IndexError):
                        pass
            if scores:
                return scores
        sentences = text.count(".")
        return {"fluency": 0.7, "coherence": 0.6, "completeness": min(1.0, sentences / 5.0)}
