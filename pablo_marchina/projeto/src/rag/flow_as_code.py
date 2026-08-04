from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class FlowAsCode:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._flow_steps: list[dict[str, Any]] = []

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        step_name = kwargs.get("step_name", "process")
        for ctx in contexts:
            self._flow_steps.append({"step": step_name, "context_id": ctx.chunk_id, "score": ctx.relevance_score})

            self._flow_steps = self._flow_steps[-1000:]
        return contexts
