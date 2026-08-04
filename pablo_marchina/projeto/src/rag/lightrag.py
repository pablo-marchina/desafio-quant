from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class Lightrag:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            unique_entities: set[str] = set()
            for ctx in contexts:
                entities = {w for w in ctx.content.split() if w[0].isupper() and len(w) > 2}

                unique_entities.update(entities)

                for ctx in contexts:
                    entity_density = sum(1 for w in ctx.content.split() if w in unique_entities) / max(
                        len(ctx.content.split()), 1
                    )

                    ctx.relevance_score = round(ctx.relevance_score * (0.7 + 0.3 * min(entity_density * 10, 1.0)), 4)

        return contexts
