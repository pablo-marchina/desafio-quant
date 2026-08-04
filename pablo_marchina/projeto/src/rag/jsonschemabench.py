from __future__ import annotations

import json
from typing import Any

from src.rag.schemas import RetrievedContext


class Jsonschemabench:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            for ctx in contexts:
                json_score = self._score_json_validity(ctx.content[:1024])

                ctx.relevance_score = round(ctx.relevance_score * json_score, 4)

        return contexts

    @staticmethod
    def _score_json_validity(text: str) -> float:
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                return min(1.0, 0.5 + 0.1 * len(obj))
            if isinstance(obj, list):
                return min(1.0, 0.5 + 0.05 * len(obj))
            return 0.5
        except (json.JSONDecodeError, ValueError):
            open_brace = text.count("{")
            close_brace = text.count("}")
            if open_brace > 0 or close_brace > 0:
                ratio = min(open_brace, close_brace) / max(open_brace, close_brace, 1)
                return round(0.3 * ratio, 4)
            return 0.3
