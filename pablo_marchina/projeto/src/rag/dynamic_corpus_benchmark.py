from __future__ import annotations

import time
from typing import Any

from src.rag.schemas import RetrievedContext


class DynamicCorpusBenchmark:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._corpus_age: dict[str, float] = {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            now = time.time()
            for ctx in contexts:
                prev_time = self._corpus_age.get(ctx.chunk_id)

                if prev_time is not None:
                    age_delta = now - prev_time

                    if age_delta > 3600:
                        ctx.relevance_score = round(ctx.relevance_score * 0.8, 4)

                        self._corpus_age[ctx.chunk_id] = now

        return contexts
