from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext

_HALLUC_KEYWORDS = {
    "coming soon",
    "announced",
    "planned",
    "expected",
    "vision",
    "future release",
    "roadmap",
    "upcoming",
    "in development",
    "not yet available",
    "proposed",
    "concept",
    "prototype",
    "theoretical",
    "would enable",
    "could enable",
}


class HallucinationDetectionHead:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            for ctx in contexts:
                title_lower = ctx.title.lower()

                content_lower = ctx.content[:512].lower()

                hallucination_signals = 0

                for keyword in _HALLUC_KEYWORDS:
                    if keyword in title_lower or keyword in content_lower:
                        hallucination_signals += 1

                        if hallucination_signals > 0:
                            penalty = 1.0 - (0.15 * min(hallucination_signals, 5))

                            ctx.relevance_score = round(ctx.relevance_score * max(0.1, penalty), 4)

        return contexts
