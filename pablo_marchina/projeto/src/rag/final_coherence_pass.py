"""Final coherence pass — final coherence check."""

from __future__ import annotations

from collections import Counter
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class FinalCoherencePassConfig(BaseModel):
    coherence_boost: float = 0.08


class FinalCoherencePass:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = FinalCoherencePassConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            all_words = []
            for ctx in contexts:
                all_words.extend(w.lower() for w in ctx.content.split() if len(w) > 3)

                freq = Counter(all_words)
                common_terms = {w for w, c in freq.most_common(10)}
                for ctx in contexts:
                    ctx_words = set(w.lower() for w in ctx.content.split() if len(w) > 3)

                    overlap = len(ctx_words & common_terms) / max(1, len(common_terms))

                    coherence_score = overlap * self.cfg.coherence_boost

                    ctx.relevance_score = round(min(1.0, ctx.relevance_score + coherence_score), 4)

        return contexts
