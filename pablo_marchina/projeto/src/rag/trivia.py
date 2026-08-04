from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_QUESTION_WORDS = {"what", "who", "where", "when", "why", "how", "which", "whose", "whom"}


class Trivia:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            query = str(kwargs.get("query", "")).lower()
            if not query:
                return contexts

                is_trivia = self._is_trivia_query(query)
                for ctx in contexts:
                    if is_trivia:
                        answer_count = len(
                            re.findall(
                                r"\b(?:" + "|".join(re.escape(w) for w in query.split()) + r")\b",
                                ctx.content,
                                re.IGNORECASE,
                            )
                        )

                        if answer_count > 0:
                            ctx.relevance_score = round(ctx.relevance_score * (1.0 + 0.1 * min(answer_count, 5)), 4)

        return contexts

    @staticmethod
    def _is_trivia_query(query: str) -> bool:
        return any(query.startswith(q) for q in _QUESTION_WORDS)
