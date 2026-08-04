"""outdated evidence detector

Hypothesis: Evaluate whether outdated evidence detector improves final product output without paid dependency.
Category: 8.39 Temporal RAG and Currentness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class OutdatedEvidenceDetector:
    """outdated evidence detector"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        import re as _re
        from datetime import datetime

        now = datetime.now()

        for ctx in contexts:
            years = _re.findall(r"(20\d{2})", ctx.content)

            if years:
                latest = max(int(y) for y in years)

                if now.year - latest > 3:
                    ctx.relevance_score = max(0.0, ctx.relevance_score - 0.2)

                elif now.year - latest > 1:
                    ctx.relevance_score = max(0.0, ctx.relevance_score - 0.08)

            stale_signal = any(w in ctx.content.lower() for w in ["deprecated", "legacy", "outdated", "old version"])

            if stale_signal:
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.15)

        return contexts
