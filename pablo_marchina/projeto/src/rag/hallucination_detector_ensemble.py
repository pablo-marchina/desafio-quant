from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class HallucinationDetectorEnsemble:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._detectors = [
            ("keyword_future", self._detect_future_keywords),
            ("keyword_vague", self._detect_vague_language),
            ("keyword_negation", self._detect_negation_conflict),
        ]

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            for ctx in contexts:
                signals = 0

                for _name, detector in self._detectors:
                    if detector(ctx.content[:512]):
                        signals += 1

                        if signals > 0:
                            penalty = 1.0 - (0.2 * signals)

                            ctx.relevance_score = round(ctx.relevance_score * max(0.1, penalty), 4)

        return contexts

    @staticmethod
    def _detect_future_keywords(text: str) -> bool:
        words = {"will", "future", "upcoming", "planned", "expected", "soon", "roadmap", "vision"}
        return bool(set(text.lower().split()) & words)

    @staticmethod
    def _detect_vague_language(text: str) -> bool:
        words = {"maybe", "perhaps", "possibly", "might", "could", "seems", "appears", "may"}
        count = sum(1 for w in words if w in text.lower().split())
        return count >= 2

    @staticmethod
    def _detect_negation_conflict(text: str) -> bool:
        lower = text.lower()
        has_positive = any(w in lower for w in ["is", "are", "was", "were", "has", "have", "does", "do"])
        has_negative = any(w in lower for w in ["not", "no", "never", "none", "nobody"])
        return has_positive and has_negative
