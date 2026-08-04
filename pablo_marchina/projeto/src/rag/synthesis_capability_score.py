"""Synthesis capability score — score synthesis capability."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class SynthesisCapabilityScoreConfig(BaseModel):
    synthesis_weight: float = 0.3


class SynthesisCapabilityScore:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = SynthesisCapabilityScoreConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            for ctx in contexts:
                content_len = len(ctx.content.split())

                sentence_count = max(1, ctx.content.count("."))

                avg_sentence_len = content_len / sentence_count

                synthesis_readiness = min(1.0, avg_sentence_len / 30)

                ctx.relevance_score = round(
                    (1.0 - self.cfg.synthesis_weight) * ctx.relevance_score
                    + self.cfg.synthesis_weight * synthesis_readiness,
                    4,
                )

        return contexts
