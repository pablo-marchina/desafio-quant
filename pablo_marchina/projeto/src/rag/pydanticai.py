from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class Pydanticai:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            for ctx in contexts:
                structured_score = self._score_structured(ctx.content[:1024])

                ctx.relevance_score = round(ctx.relevance_score * structured_score, 4)

        return contexts

    @staticmethod
    def _score_structured(text: str) -> float:
        dict_like = text.count(":") >= 3 and "{" in text
        comma_sep = text.count(",") >= 3
        has_types = any(t in text for t in ["str", "int", "float", "bool", "List", "Dict", "Optional"])
        score = 0.3
        if dict_like:
            score += 0.3
        if comma_sep:
            score += 0.2
        if has_types:
            score += 0.2
        return round(min(1.0, score), 4)
