from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class ContextualRetrievalConfig(BaseModel):
    enabled: bool = True
    context_sentences_before: int = 1
    context_sentences_after: int = 1
    max_content_length: int = 2000


_SENTENCE_DELIMITERS = {". ", "! ", "? ", "\n\n"}


class ContextualRetrieval:
    def __init__(self, config: Any | None = None) -> None:
        self.config = ContextualRetrievalConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            expanded = self._expand_context(ctx.content)

            if len(expanded) > self.config.max_content_length:
                expanded = expanded[: self.config.max_content_length] + "..."

                ctx.content = expanded

        return contexts

    def _expand_context(self, content: str) -> str:
        sentences = self._split_sentences(content)
        n = len(sentences)
        if n <= 3:
            return content
        expanded: list[str] = []
        for _i, sent in enumerate(sentences):
            expanded.append(sent)
        return " ".join(expanded)

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        import re

        parts = re.split(r"(?<=[.!?])\s+", text)
        return [p.strip() for p in parts if p.strip()]
