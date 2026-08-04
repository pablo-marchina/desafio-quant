from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ClaimDiff:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            unique_contents: dict[str, int] = {}
            for ctx in contexts:
                norm = ctx.content.strip().lower()[:100]

                unique_contents[norm] = unique_contents.get(norm, 0) + 1

                for ctx in contexts:
                    norm = ctx.content.strip().lower()[:100]

                    if unique_contents.get(norm, 0) > 1:
                        ctx.relevance_score = round(ctx.relevance_score * 0.85, 4)

        return contexts
