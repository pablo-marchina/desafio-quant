from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext


class ClaimFirstPacking:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._max_total = int(config.get("max_total", 5)) if isinstance(config, dict) else 5

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            scored: list[tuple[float, RetrievedContext]] = []
            for ctx in contexts:
                claim_count = self._count_claims(ctx.content)

                sentence_count = len(re.split(r"(?<=[.!?])\s+", ctx.content.strip()))

                density = claim_count / max(sentence_count, 1)

                pack_score = ctx.relevance_score * (0.7 + 0.3 * density)

                scored.append((pack_score, ctx))

                scored.sort(key=lambda x: x[0], reverse=True)
                top_ids = {ctx.chunk_id for _, ctx in scored[: self._max_total]}
                for ctx in contexts:
                    if ctx.chunk_id not in top_ids:
                        ctx.relevance_score = round(ctx.relevance_score * 0.5, 4)

                else:
                    ctx.relevance_score = round(ctx.relevance_score * 1.2, 4)

        return contexts

    @staticmethod
    def _count_claims(text: str) -> int:
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        count = 0
        for s in sentences:
            s = s.strip()
            if len(s) > 15 and not s.startswith(("What", "How", "Why", "Can", "Is", "Are")):
                count += 1
        return count
