from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class AtomicFactExtractionConfig(BaseModel):
    enabled: bool = True
    max_facts_per_chunk: int = 10
    min_fact_length: int = 10


class AtomicFactExtraction:
    def __init__(self, config: Any | None = None) -> None:
        self.config = AtomicFactExtractionConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        result: list[RetrievedContext] = []
        for ctx in contexts:
            facts = self._extract_facts(ctx.content)
            for i, fact in enumerate(facts[: self.config.max_facts_per_chunk]):
                new_ctx = ctx.model_copy(deep=True)
                new_ctx.chunk_id = f"{ctx.chunk_id}_fact_{i}"
                new_ctx.content = fact
                new_ctx.relevance_score = round(min(ctx.relevance_score * 1.1, 1.0), 4)
                result.append(new_ctx)
        return result

    @staticmethod
    def _extract_facts(text: str) -> list[str]:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        facts: list[str] = []
        for sent in sentences:
            sent = sent.strip()
            if not sent or len(sent) < 10:
                continue
            facts.append(sent)
        return facts
