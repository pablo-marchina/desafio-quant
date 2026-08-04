from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class PromptRegistry:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._registry: dict[str, dict[str, Any]] = {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        prompt_name = kwargs.get("prompt_name", "default")
        entry = {
            "name": prompt_name,
            "num_contexts": len(contexts),
            "avg_score": round(sum(c.relevance_score for c in contexts) / max(len(contexts), 1), 4),
            "context_ids": [c.chunk_id for c in contexts],
        }
        self._registry[prompt_name] = entry
        return contexts
