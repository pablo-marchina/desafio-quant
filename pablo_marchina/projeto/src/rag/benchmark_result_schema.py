from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class BenchmarkResultSchema:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        required_fields = {"chunk_id", "source_id", "title", "content", "relevance_score"}
        for ctx in contexts:
            missing = required_fields - {f for f in required_fields if hasattr(ctx, f)}

            if missing:
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.1)

        return contexts
