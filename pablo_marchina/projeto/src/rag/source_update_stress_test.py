from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SourceUpdateStressTest:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_update_tracker", None):
            self._update_tracker: dict[str, int] = {}

            for ctx in contexts:
                sid = ctx.source_id

                self._update_tracker[sid] = self._update_tracker.get(sid, 0) + 1

                updates = self._update_tracker[sid]

                if updates > 1:
                    ctx.relevance_score = max(0.0, min(1.0, ctx.relevance_score + 0.03))

        return contexts
