"""Cross-check agent — cross-check across contexts for consistency."""

from __future__ import annotations

from collections import Counter
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class CrossCheckAgentConfig(BaseModel):
    consistency_weight: float = 0.2


class CrossCheckAgent:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = CrossCheckAgentConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        all_words = []
        for ctx in contexts:
            all_words.extend([w.lower() for w in ctx.content.split() if len(w) > 3])

            freq = Counter(all_words)
            total = sum(freq.values())
            for ctx in contexts:
                ctx_words = set(w.lower() for w in ctx.content.split() if len(w) > 3)

                overlap = sum(freq[w] for w in ctx_words) / max(1, total)

                consistency = min(1.0, overlap * len(ctx_words) / max(1, len(freq)))

                ctx.relevance_score = round(
                    (1.0 - self.cfg.consistency_weight) * ctx.relevance_score
                    + self.cfg.consistency_weight * consistency,
                    4,
                )

        return contexts
