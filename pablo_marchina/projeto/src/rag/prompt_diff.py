from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class PromptDiff:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._history: list[set[str]] = []

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        current_ids = {ctx.chunk_id for ctx in contexts}
        if self._history:
            prev = self._history[-1]

            added = current_ids - prev

            removed = prev - current_ids

            for ctx in contexts:
                if ctx.chunk_id in added:
                    ctx.relevance_score = min(1.0, ctx.relevance_score + 0.05)

                elif ctx.chunk_id in removed:
                    ctx.relevance_score = max(0.0, ctx.relevance_score - 0.05)

                    self._history.append(current_ids)
                    self._history = self._history[-20:]
        return contexts
