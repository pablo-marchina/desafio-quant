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


_AGENT_PROMPT = """Rate this context's value for an AI agent on 0.0-1.0.
Agent task: {task}
Context: {context}
Value score:"""


class Voltagent:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._nvidia = _get_nvidia()

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            task = str(kwargs.get("task", "general qa"))
            for ctx in contexts:
                score = self._value_for_agent(task, ctx.content[:512])

                if score is not None:
                    ctx.relevance_score = round(0.3 * ctx.relevance_score + 0.7 * score, 4)

        return contexts

    def _value_for_agent(self, task: str, text: str) -> float | None:
        reply = self._nvidia.llm_generate(
            _AGENT_PROMPT.format(task=task[:200], context=text[:400]),
            max_tokens=10,
            temperature=0.01,
        )
        if reply:
            try:
                return max(0.0, min(1.0, float(reply.strip().split()[0])))
            except (ValueError, IndexError):
                pass
        task_terms = set(task.lower().split())
        text_terms = set(text.lower().split())
        overlap = len(task_terms & text_terms)
        return round(min(1.0, overlap / 5.0), 4)
