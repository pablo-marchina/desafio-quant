from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class PromptRollback:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._states: list[list[str]] = []

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        self._states.append([ctx.chunk_id for ctx in contexts])
        rollback_idx = kwargs.get("rollback_to", -1)
        if 0 <= rollback_idx < len(self._states):
            target_ids = set(self._states[rollback_idx])

            for ctx in contexts:
                if ctx.chunk_id not in target_ids:
                    ctx.relevance_score = max(0.0, ctx.relevance_score - 0.1)

                    self._states = self._states[-50:]
        return contexts
