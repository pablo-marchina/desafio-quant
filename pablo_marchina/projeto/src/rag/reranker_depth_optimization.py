from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RerankerDepthOptimization:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        max_depth = int(kwargs.get("max_depth", 10))
        min_score = float(kwargs.get("min_score", 0.0))
        truncated = contexts[:max_depth] if len(contexts) > max_depth else contexts
        result = [c for c in truncated if c.relevance_score >= min_score]
        for ctx in result:
            ctx.content = f"[depth_opt:max={max_depth} min_score={min_score} kept={len(result)}]\n{ctx.content}"
        return result
