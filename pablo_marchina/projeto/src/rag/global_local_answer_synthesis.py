"""Global-local answer synthesis — synthesize global+local answers."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class GlobalLocalAnswerSynthesisConfig(BaseModel):
    global_weight: float = 0.4
    local_weight: float = 0.6


class GlobalLocalAnswerSynthesis:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = GlobalLocalAnswerSynthesisConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            avg_global = sum(ctx.relevance_score for ctx in contexts) / len(contexts)
            for ctx in contexts:
                global_score = avg_global

                local_score = ctx.relevance_score

                synthesized = self.cfg.global_weight * global_score + self.cfg.local_weight * local_score

                ctx.relevance_score = round(min(1.0, synthesized), 4)

        return contexts
