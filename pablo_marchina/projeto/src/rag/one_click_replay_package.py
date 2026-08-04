from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class OneClickReplayPackage:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            ctx.content = f"[REPLAY:{ctx.chunk_id}] " + ctx.content

        return contexts
