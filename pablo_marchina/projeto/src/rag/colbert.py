"""Local ColBERT-style late-interaction reranker.

This module intentionally provides a free, self-hosted approximation of
ColBERT's max-sim late interaction using token overlap over the retrieved
contexts.  It does not claim to be the full neural ColBERT model; it gives the
runtime a deterministic, auditable late-interaction signal when no external
reranker is configured.
"""

from __future__ import annotations

import math
import re
from typing import Any

from src.rag.schemas import RetrievedContext


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-zA-Z0-9_]+", text.lower()) if len(t) > 2]


class Colbert:
    """Free ColBERT-style late-interaction reranker."""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query = str(kwargs.get("query") or " ".join(c.product for c in contexts[:3]))
        q_tokens = _tokens(query)
        if not contexts or not q_tokens:
            return contexts
        q_set = set(q_tokens)
        for ctx in contexts:
            c_tokens = _tokens(f"{ctx.title} {ctx.product} {' '.join(ctx.gap_types)} {ctx.content}")
            if not c_tokens:
                continue
            # Late-interaction approximation: for each query token, reward the
            # strongest exact-token match in the passage, normalized by query length.
            c_set = set(c_tokens)
            exact = sum(1.0 for token in q_tokens if token in c_set)
            density = exact / math.sqrt(max(1, len(q_tokens)) * max(1, len(c_set)))
            ctx.relevance_score = round(min(1.0, float(ctx.relevance_score) + density * 0.25), 4)
        return sorted(contexts, key=lambda c: c.relevance_score, reverse=True)
