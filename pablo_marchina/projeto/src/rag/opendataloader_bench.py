from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext

_CHUNK_SIZE = 1000


class OpendataloaderBench:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        total_chars = sum(len(ctx.content) for ctx in contexts)
        chunk_count = max(1, round(total_chars / _CHUNK_SIZE))
        load_score = round(min(chunk_count / max(len(contexts), 1) * 0.5, 1.0), 4) if contexts else 0.0
        for ctx in contexts:
            ctx.content = f"[opendataloader:chunks={chunk_count} load_score={load_score}]\n{ctx.content}"
        return contexts
