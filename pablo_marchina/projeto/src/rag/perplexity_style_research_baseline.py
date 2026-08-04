"""perplexity-style research baseline

Hypothesis: Evaluate whether perplexity-style research baseline improves final product output without paid dependency.
Category: 8.51 Search Backend Benchmarks
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class PerplexityStyleResearchBaseline:
    """perplexity-style research baseline"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        research_signals = ["source", "according to", "research", "study", "paper", "publication", "journal", "doi"]

        for ctx in contexts:
            signal_count = sum(1 for s in research_signals if s.lower() in ctx.content.lower())

            has_citation = bool(ctx.url)

            score = (signal_count * 0.15) + (0.2 if has_citation else 0.0)

            ctx.relevance_score = min(1.0, score)

        return contexts
