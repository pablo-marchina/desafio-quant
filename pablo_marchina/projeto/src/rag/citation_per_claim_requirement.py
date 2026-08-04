"""citation per claim requirement

Hypothesis: Evaluate whether citation per claim requirement improves final product output without paid dependency.
Category: 8.44 Output Versioning and Audit
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class CitationPerClaimRequirement:
    """citation per claim requirement"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        import re as _re

        for ctx in contexts:
            claims = [s.strip() for s in ctx.content.split(".") if s.strip() and len(s) > 20]

            citations = _re.findall(r"\[\d+\]|\[.*?\]|\(.*?(?:doi|arxiv|http).*?\)", ctx.content)

            ratio = len(citations) / max(len(claims), 1)

            if ratio < 0.5:
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.1)

            else:
                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.05)

        return contexts
