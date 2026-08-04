from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext

_KNOWN_INJECTION_CORPUS = [
    "ignore all previous instructions",
    "forget everything above",
    "you are now a free AI",
    "do anything now",
    "pretend you are",
    "character play",
    "override your programming",
    "you must obey",
    "no filters",
    "DAN mode",
]


class PromptInjectionCorpus:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._corpus = list(set(_KNOWN_INJECTION_CORPUS + self.config.get("extra_patterns", [])))
        self._threshold = int(self.config.get("corpus_threshold", 1))

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            content_lower = ctx.content.lower()

            matches = sum(1 for pattern in self._corpus if pattern in content_lower)

            if matches >= self._threshold:
                ctx.relevance_score = round(max(0.0, ctx.relevance_score - 0.3 * matches), 4)

        return contexts
