from __future__ import annotations

import importlib
from typing import Any

from src.rag.schemas import RetrievedContext


class Sqlalchemy:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._lib_available: bool | None = None

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if self._lib_available is None:
            try:
                importlib.import_module("sqlalchemy")

                self._lib_available = True

            except ImportError:
                self._lib_available = False

                tech_keywords = self.config.get("tech_keywords", ["sqlalchemy", "orm", "session", "query", "model"])
                for ctx in contexts:
                    content_lower = ctx.content.lower()

                    match_count = sum(1 for kw in tech_keywords if kw in content_lower)

                    ctx.relevance_score = min(1.0, ctx.relevance_score + match_count * 0.08)

        return contexts
