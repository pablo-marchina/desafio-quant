from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class Hipporag:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            hippo_scores: list[tuple[int, float]] = []
            for i, ctx in enumerate(contexts):
                noun_phrases = [w for w in ctx.content.split() if w[0].isupper() and len(w) > 2]

                score = len(noun_phrases) * 0.1

                hippo_scores.append((i, score))

                for i, score in hippo_scores:
                    if i < len(contexts):
                        contexts[i].relevance_score = round(
                            contexts[i].relevance_score * (0.5 + 0.5 * min(1.0, score)), 4
                        )

        return contexts
