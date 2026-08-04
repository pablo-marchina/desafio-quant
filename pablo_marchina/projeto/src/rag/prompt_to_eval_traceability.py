from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class PromptToEvalTraceability:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._traceability: list[dict[str, Any]] = []

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        trace: dict[str, Any] = {
            "prompt_name": kwargs.get("prompt_name", "default"),
            "eval_name": kwargs.get("eval_name", "unknown_eval"),
            "num_contexts": len(contexts),
            "avg_score": round(sum(c.relevance_score for c in contexts) / max(len(contexts), 1), 4),
            "context_ids": [c.chunk_id for c in contexts],
        }
        self._traceability.append(trace)
        self._traceability = self._traceability[-500:]
        return contexts
