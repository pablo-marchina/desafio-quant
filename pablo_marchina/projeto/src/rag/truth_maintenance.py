from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class TruthMaintenanceSystemConfig(BaseModel):
    enabled: bool = True
    revision_decay: float = 0.1
    max_revisions: int = 5


class TruthMaintenanceSystem:
    def __init__(self, config: Any | None = None) -> None:
        self.config = TruthMaintenanceSystemConfig.model_validate(config or {})
        self._beliefs: dict[str, dict[str, Any]] = {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            key = ctx.chunk_id

            old_belief = self._beliefs.get(key, {})

            old_score = old_belief.get("score", 0.0)

            revision_count = old_belief.get("revisions", 0)

            if revision_count > 0 and ctx.relevance_score != old_score:
                revision_count += 1

                decay = self.config.revision_decay * min(revision_count, self.config.max_revisions)

                ctx.relevance_score = round(max(0.0, ctx.relevance_score - decay), 4)

                self._beliefs[key] = {
                    "score": ctx.relevance_score,
                    "revisions": old_belief.get("revisions", 0) + 1,
                }

        return contexts
