"""domain keyphrase extraction

Hypothesis: Evaluate whether domain keyphrase extraction improves final product output without paid dependency.
Category: 8.50 Terminology and Domain Adaptation
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class DomainKeyphraseExtraction:
    """domain keyphrase extraction"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_keyphrases", None):
            self._keyphrases: list[str] = []

        import re as _re

        for ctx in contexts:
            phrases = _re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", ctx.content)

            phrases = [p for p in phrases if len(p.split()) > 1]

            self._keyphrases.extend(phrases)

            coverage = len(set(phrases)) / max(len(phrases), 1)

            ctx.relevance_score = min(1.0, ctx.relevance_score + coverage * 0.03)

        self._keyphrases = list(set(self._keyphrases))[-200:]

        return contexts
