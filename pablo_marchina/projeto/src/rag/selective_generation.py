from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SelectiveGeneration:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._gen_threshold = float(config.get("gen_threshold", 0.6)) if isinstance(config, dict) else 0.6

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            has_high_quality = any(ctx.relevance_score >= self._gen_threshold for ctx in contexts)
            if not has_high_quality:
                for ctx in contexts:
                    ctx.relevance_score = round(ctx.relevance_score * 0.5, 4)

        return contexts
