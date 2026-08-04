from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class Mmrag:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            for ctx in contexts:
                content = ctx.content

                has_tabular = any(c in content for c in ["|", "\t", ","])

                has_structured = ctx.product in ("table", "chart", "structured")

                if has_tabular or has_structured:
                    ctx.relevance_score = round(ctx.relevance_score * 1.2, 4)

        return contexts
