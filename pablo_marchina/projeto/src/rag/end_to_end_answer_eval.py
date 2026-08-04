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


_ANSWER_EVAL_PROMPT = """Rate the quality of this answer on a scale of 0.0 to 1.0.
Consider: accuracy, completeness, relevance, and clarity.

Answer: {answer}
Quality score:"""


class EndToEndAnswerEval:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._nvidia = _get_nvidia()

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            combined = " ".join(ctx.content for ctx in contexts)
            score = self._evaluate_answer(combined[:1024])
            if score is not None:
                for ctx in contexts:
                    ctx.relevance_score = round(ctx.relevance_score * score, 4)

        return contexts

    def _evaluate_answer(self, answer: str) -> float | None:
        reply = self._nvidia.llm_generate(
            _ANSWER_EVAL_PROMPT.format(answer=answer[:800]), max_tokens=10, temperature=0.01
        )
        if reply:
            try:
                return max(0.0, min(1.0, float(reply.strip().split()[0])))
            except (ValueError, IndexError):
                pass
        char_count = len(answer)
        return round(min(1.0, char_count / 500.0), 4)
