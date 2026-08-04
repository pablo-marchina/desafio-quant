from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

NON_WORD = re.compile(r"[^a-zA-Záéíóúâêîôûàèìòùäëïöüçñ]+")


class ReadabilityLxml:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    @staticmethod
    def _readability_score(text: str) -> float:
        words = [w for w in NON_WORD.split(text.lower()) if w]
        if not words:
            return 0.0
        sentences = max(len(re.findall(r"[.!?]+", text)), 1)
        syllables = sum(max(1, len(re.findall(r"[aeiouáéíóúâêîôûàèìòùäëïöü]+", w))) for w in words)
        avg_words_per_sent = len(words) / sentences
        avg_syllables_per_word = syllables / len(words)
        score = 206.835 - 1.015 * avg_words_per_sent - 84.6 * avg_syllables_per_word
        return round(max(0.0, min(100.0, score)), 2)

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            score = self._readability_score(ctx.content)
            ctx.content = f"[readability:{score}]\n{ctx.content}"
        return contexts
