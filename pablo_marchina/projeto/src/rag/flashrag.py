from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class Flashrag:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            for ctx in contexts:
                key_terms = {"nvidia", "cuda", "gpu", "ai", "deep learning", "machine learning", "tensorrt", "triton"}

                content_lower = ctx.content.lower()

                match_count = sum(1 for t in key_terms if t in content_lower)

                if match_count > 0:
                    ctx.relevance_score = round(ctx.relevance_score * (1.0 + 0.05 * match_count), 4)

        return contexts
