from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class PromptAssembler:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._history: list[str] = []

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        section = kwargs.get("section", "context")
        assembled = f"=== {section} ===\n"
        for ctx in contexts:
            assembled += f"[{ctx.chunk_id}] (score={ctx.relevance_score:.2f}) {ctx.content[:500]}\n\n"

            self._history.append(assembled)
            self._history = self._history[-50:]
        return contexts
