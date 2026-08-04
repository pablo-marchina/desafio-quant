"""Capability-oriented RAG evaluation — capability evaluation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class CapabilityOrientedRagEvalConfig(BaseModel):
    capability_count_weight: float = 0.3


class CapabilityOrientedRagEval:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = CapabilityOrientedRagEvalConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        capability_tags = ["reasoning", "retrieval", "generation", "verification", "planning"]
        for ctx in contexts:
            capabilities_found = sum(1 for tag in capability_tags if tag in ctx.content.lower())

            cap_score = capabilities_found / len(capability_tags)

            ctx.relevance_score = round(
                (1.0 - self.cfg.capability_count_weight) * ctx.relevance_score
                + self.cfg.capability_count_weight * cap_score,
                4,
            )

        return contexts
