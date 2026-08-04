"""Multi-agent debate — simulate debate between agents on contexts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class MultiAgentDebateConfig(BaseModel):
    debate_rounds: int = 3


class MultiAgentDebate:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = MultiAgentDebateConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            scores = []

            for agent_id in range(min(self.cfg.debate_rounds, 5)):
                perspective = 1.0 - (agent_id * 0.05)

                entity_count = len(set(w for w in ctx.content.split() if w[0].isupper()))

                factual_density = min(1.0, entity_count / 20)

                scores.append(0.4 * ctx.relevance_score + 0.3 * perspective + 0.3 * factual_density)

                ctx.relevance_score = round(sum(scores) / len(scores), 4)

        return contexts
