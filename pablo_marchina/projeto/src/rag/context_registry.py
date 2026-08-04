"""Context registry — registers and tracks context usage across pipeline."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class ContextRegistryConfig(BaseModel):
    max_registered: int = 100


class ContextRegistry:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = ContextRegistryConfig.model_validate(config or {})
        self._registry: dict[str, dict[str, Any]] = {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            if ctx.chunk_id not in self._registry:
                self._registry[ctx.chunk_id] = {
                    "source_id": ctx.source_id,
                    "title": ctx.title,
                    "visit_count": 0,
                    "cumulative_score": 0.0,
                }

                entry = self._registry[ctx.chunk_id]

                entry["visit_count"] += 1

                entry["cumulative_score"] += ctx.relevance_score

                avg = entry["cumulative_score"] / entry["visit_count"]

                ctx.relevance_score = round(min(1.0, ctx.relevance_score * 0.7 + avg * 0.3), 4)

                if len(self._registry) > self.cfg.max_registered:
                    oldest = sorted(self._registry.keys())[: len(self._registry) - self.cfg.max_registered]

                    for k in oldest:
                        del self._registry[k]

        return contexts
