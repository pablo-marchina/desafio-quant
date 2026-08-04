from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class M2rag:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            for ctx in contexts:
                text_len = len(ctx.content)

                num_words = len(ctx.content.split())

                avg_word_len = text_len / max(num_words, 1)

                if avg_word_len > 7:
                    ctx.relevance_score = round(ctx.relevance_score * 0.9, 4)

                    if text_len > 2000:
                        ctx.relevance_score = round(ctx.relevance_score * 0.85, 4)

        return contexts
