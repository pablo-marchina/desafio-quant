"""Long-context final synthesis — synthesize long contexts."""

from __future__ import annotations

from collections import Counter
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class LongContextFinalSynthesisConfig(BaseModel):
    synthesis_ratio: float = 0.5


class LongContextFinalSynthesis:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = LongContextFinalSynthesisConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            all_words = []
            for ctx in contexts:
                all_words.extend(ctx.content.lower().split())

                freq = Counter(all_words)
                for ctx in contexts:
                    ctx_words = ctx.content.lower().split()

                    common = sum(1 for w in set(ctx_words) if freq[w] > 1)

                    uniqueness = 1.0 - (common / max(1, len(set(ctx_words))))

                    synthesis_score = 0.5 * ctx.relevance_score + 0.5 * uniqueness

                    ctx.relevance_score = round(min(1.0, synthesis_score), 4)

        return contexts
