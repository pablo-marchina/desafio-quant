from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class PromptChangelog:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._changelog: list[dict[str, Any]] = []

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        entry: dict[str, Any] = {
            "prompt_name": kwargs.get("prompt_name", "default"),
            "change_type": kwargs.get("change_type", "update"),
            "num_contexts": len(contexts),
            "avg_score": round(sum(c.relevance_score for c in contexts) / max(len(contexts), 1), 4),
        }
        self._changelog.append(entry)
        self._changelog = self._changelog[-500:]
        return contexts
