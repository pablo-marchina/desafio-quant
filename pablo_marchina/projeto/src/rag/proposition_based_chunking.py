from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class PropositionBasedChunkingConfig(BaseModel):
    enabled: bool = True
    max_propositions_per_chunk: int = 20


class PropositionBasedChunking:
    def __init__(self, config: Any | None = None) -> None:
        self.config = PropositionBasedChunkingConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        result: list[RetrievedContext] = []
        for ctx in contexts:
            propositions = self._split_into_propositions(ctx.content)
            for i, prop in enumerate(propositions[: self.config.max_propositions_per_chunk]):
                new_ctx = ctx.model_copy(deep=True)
                new_ctx.chunk_id = f"{ctx.chunk_id}_prop_{i}"
                new_ctx.content = prop
                new_ctx.relevance_score = round(ctx.relevance_score * 0.9, 4)
                result.append(new_ctx)
        return result

    @staticmethod
    def _split_into_propositions(text: str) -> list[str]:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        propositions: list[str] = []
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            clauses = re.split(r"(?:,|;)\s*(?=which|that|where|when|who|although|because|since|while|however)", sent)
            for clause in clauses:
                clause = clause.strip()
                if clause:
                    propositions.append(clause)
        return propositions or [text]
