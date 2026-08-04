from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class HumanOverrideGovernance:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        override = kwargs.get("override", "")
        if override:
            override_score = float(kwargs.get("override_score", -1))

            if 0.0 <= override_score <= 1.0:
                for ctx in contexts:
                    ctx.relevance_score = override_score

        return contexts
