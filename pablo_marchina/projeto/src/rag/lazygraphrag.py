from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class Lazygraphrag:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            if len(contexts) < 3:
                return contexts

                for i, ctx in enumerate(contexts):
                    if i < len(contexts) - 2:
                        next_entity = {w for w in contexts[i + 1].content.split() if w[0].isupper() and len(w) > 2}

                        curr_entity = {w for w in ctx.content.split() if w[0].isupper() and len(w) > 2}

                        overlap = len(curr_entity & next_entity)

                        if overlap > 0:
                            ctx.relevance_score = round(ctx.relevance_score * (1.0 + 0.05 * overlap), 4)

        return contexts
