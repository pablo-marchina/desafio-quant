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


_EVAL_PROMPTS = [
    ("fluency", "Rate this text's fluency on 0.0-1.0. Text: {text}\nFluency:"),
    ("relevance", "Rate this text's relevance on 0.0-1.0. Text: {text}\nRelevance:"),
    ("factuality", "Rate this text's factuality on 0.0-1.0. Text: {text}\nFactuality:"),
]


class EnsembleOfEvaluators:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._nvidia = _get_nvidia()

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

        for ctx in contexts:
            scores: list[float] = []

            for _name, prompt_template in _EVAL_PROMPTS:
                reply = self._nvidia.llm_generate(
                    prompt_template.format(text=ctx.content[:400]), max_tokens=10, temperature=0.01
                )

                if reply:
                    try:
                        scores.append(max(0.0, min(1.0, float(reply.strip().split()[0]))))

                    except (ValueError, IndexError):
                        pass

                    if scores:
                        ctx.relevance_score = round(sum(scores) / len(scores), 4)

        return contexts
