"""GraphRAG hallucination benchmark — hallucination benchmark."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class GraphragHallucinationBenchmarkConfig(BaseModel):
    hallucination_penalty: float = 0.1


class GraphragHallucinationBenchmark:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = GraphragHallucinationBenchmarkConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            vague_terms = len(
                re.findall(r"\b(maybe|perhaps|possibly|could|might|seems|appears|likely)\b", ctx.content.lower())
            )

            unsupported = len(
                re.findall(r"\b(without evidence|no source|unclear|unknown|not specified)\b", ctx.content.lower())
            )

            hallucination_risk = min(1.0, (vague_terms + unsupported) * 0.1)

            penalty = hallucination_risk * self.cfg.hallucination_penalty

            ctx.relevance_score = round(max(0.0, ctx.relevance_score - penalty), 4)

        return contexts
