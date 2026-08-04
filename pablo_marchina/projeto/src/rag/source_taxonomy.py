"""source taxonomy

Hypothesis: Evaluate whether source taxonomy improves final product output without paid dependency.
Category: 8.38 Source Acquisition and Freshness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SourceTaxonomy:
    """source taxonomy"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_taxonomy", None):
            self._taxonomy: dict[str, str] = {
                "docs.nvidia.com": "documentation",
                "github.com": "code_repository",
                "arxiv.org": "academic_paper",
                "nvidia.com": "official",
                "medium.com": "blog",
                "youtube.com": "video",
            }

        cat_boost = {"documentation": 0.15, "official": 0.2, "academic_paper": 0.15, "code_repository": 0.1}

        for ctx in contexts:
            url_lower = (ctx.url or "").lower()

            category = "unknown"

            for domain, cat in self._taxonomy.items():
                if domain in url_lower:
                    category = cat

                    break

            ctx.relevance_score = min(1.0, ctx.relevance_score + cat_boost.get(category, 0.0))

        return contexts
