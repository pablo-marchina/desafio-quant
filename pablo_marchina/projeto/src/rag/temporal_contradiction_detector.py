"""temporal contradiction detector

Hypothesis: Evaluate whether temporal contradiction detector improves final product output without paid dependency.
Category: 8.39 Temporal RAG and Currentness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class TemporalContradictionDetector:
    """temporal contradiction detector"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_temporal_claims", None):
            self._temporal_claims: list[tuple[str, str, float]] = []

        import re as _re

        for ctx in contexts:
            years = _re.findall(r"(20\d{2})", ctx.content)

            for y in years:
                for prev_content, prev_year, _prev_score in self._temporal_claims:
                    if prev_year != y:
                        common_terms = set(prev_content.split()) & set(ctx.content.split())

                        if len(common_terms) > 5:
                            ctx.relevance_score = max(0.0, ctx.relevance_score - 0.1)

                self._temporal_claims.append((ctx.content[:200], y, ctx.relevance_score))

        self._temporal_claims = self._temporal_claims[-200:]

        return contexts
