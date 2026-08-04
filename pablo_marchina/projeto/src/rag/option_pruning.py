from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class OptionPruning:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        min_score = self.config.get("min_score", 0.25)
        max_options = self.config.get("max_options", 20)
        dedup_key = kwargs.get("dedup_key", "source_id")
        seen: set[str] = set()
        pruned: list[RetrievedContext] = []
        for ctx in contexts:
            if ctx.relevance_score < min_score:
                continue
            key_val = getattr(ctx, dedup_key, ctx.chunk_id)
            if key_val in seen:
                continue
            seen.add(key_val)
            pruned.append(ctx)
            if len(pruned) >= max_options:
                break
        return pruned
