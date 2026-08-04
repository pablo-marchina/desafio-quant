"""Decomposition prompting — decompose complex contexts into sub-problems."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class DecompositionPromptingConfig(BaseModel):
    max_sub_contexts: int = 3


class DecompositionPrompting:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = DecompositionPromptingConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        result = []
        for ctx in contexts:
            gap_types = ctx.gap_types
            if len(gap_types) <= 1:
                result.append(ctx)
                continue
            sentences = [
                s.strip() for s in ctx.content.replace("!", ".").replace("?", ".").split(".") if len(s.strip()) > 20
            ]
            if len(sentences) < 2:
                result.append(ctx)
                continue
            chunk_size = max(1, len(sentences) // min(len(gap_types), self.cfg.max_sub_contexts))
            for i, gap in enumerate(gap_types[: self.cfg.max_sub_contexts]):
                start = i * chunk_size
                chunk_sents = sentences[start : start + chunk_size]
                if not chunk_sents:
                    continue
                sub = ctx.model_copy(deep=True)
                sub.content = ". ".join(chunk_sents) + "."
                sub.gap_types = [gap]
                sub.chunk_id = f"{ctx.chunk_id}_sub{i}"
                sub.relevance_score = round(ctx.relevance_score * (1.0 - i * 0.1), 4)
                result.append(sub)
            if len(gap_types) > self.cfg.max_sub_contexts:
                result.append(ctx)
        return result
