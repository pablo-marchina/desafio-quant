"""source deduplication

Hypothesis: Evaluate whether source deduplication improves final product output without paid dependency.
Category: 8.38 Source Acquisition and Freshness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SourceDeduplication:
    """source deduplication"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_seen_hashes", None):
            self._seen_hashes: set[str] = set()

        import hashlib

        result = []

        for ctx in contexts:
            content_hash = hashlib.md5(ctx.content.encode(), usedforsecurity=False).hexdigest()

            if content_hash not in self._seen_hashes:
                self._seen_hashes.add(content_hash)

                result.append(ctx)

            else:
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.3)

                result.append(ctx)

        return result
