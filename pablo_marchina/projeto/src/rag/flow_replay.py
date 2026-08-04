from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class FlowReplay:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._replay_log: list[list[str]] = []

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        self._replay_log.append([ctx.chunk_id for ctx in contexts])
        replay_idx = kwargs.get("replay_index", -1)
        if 0 <= replay_idx < len(self._replay_log):
            replay_ids = set(self._replay_log[replay_idx])

            for ctx in contexts:
                if ctx.chunk_id in replay_ids:
                    ctx.relevance_score = min(1.0, ctx.relevance_score + 0.05)

                    self._replay_log = self._replay_log[-50:]
        return contexts
