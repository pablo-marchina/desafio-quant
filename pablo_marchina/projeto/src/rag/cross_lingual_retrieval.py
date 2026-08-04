from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext

_LANG_DETECT_SIGNALS: dict[str, list[str]] = {
    "pt": ["o", "a", "os", "as", "um", "uma", "de", "do", "da", "em", "para", "com", "por"],
    "en": ["the", "a", "an", "of", "in", "to", "for", "with", "on", "at", "by", "is", "are"],
    "es": ["el", "la", "los", "las", "un", "una", "de", "en", "para", "con", "por"],
    "fr": ["le", "la", "les", "un", "une", "de", "du", "des", "en", "pour", "avec"],
    "de": ["der", "die", "das", "ein", "eine", "von", "mit", "für", "auf", "ist"],
    "ja": ["の", "を", "は", "が", "に", "へ", "と", "から"],
    "zh": ["的", "了", "在", "是", "我", "有", "不", "人"],
}


class CrossLingualRetrievalConfig(BaseModel):
    enabled: bool = True
    target_language: str = "en"
    promote_target_language: bool = True
    lang_boost: float = 0.15


class CrossLingualRetrieval:
    def __init__(self, config: Any | None = None) -> None:
        self.config = CrossLingualRetrievalConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            lang = self._detect_language(ctx.content)

            if lang == self.config.target_language and self.config.promote_target_language:
                ctx.relevance_score = round(min(ctx.relevance_score + self.config.lang_boost, 1.0), 4)

        return contexts

    @staticmethod
    def _detect_language(text: str) -> str:
        words = text.lower().split()
        if not words:
            return "en"
        scores: dict[str, int] = {}
        for lang, signals in _LANG_DETECT_SIGNALS.items():
            scores[lang] = sum(1 for s in signals if s in words)
        if scores:
            return max(scores, key=lambda k: scores[k])
        return "en"
