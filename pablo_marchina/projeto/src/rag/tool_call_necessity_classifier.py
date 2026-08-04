"""_tool-call necessity classifier_

Hypothesis: Evaluate whether tool-call necessity classifier improves final product output without paid dependency.
Category: 8.35 Agentic RAG and Multi-Agent Verification
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ToolCallNecessityClassifier:
    """_tool-call necessity classifier_"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._classification_log: list[dict] = []

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            necessity_signals = ["required", "necessary", "need to", "must", "essential", "critical"]

            redundancy_signals = ["already known", "previously retrieved", "already have", "duplicate"]

            necessary = sum(1 for s in necessity_signals if s in ctx.content.lower())

            redundant = sum(1 for s in redundancy_signals if s in ctx.content.lower())

            necessity_score = (necessary - redundant) / max((necessary + redundant), 1)

            self._classification_log.append(
                {
                    "chunk_id": ctx.chunk_id,
                    "necessary": necessary,
                    "redundant": redundant,
                    "necessity_score": necessity_score,
                }
            )

            self._classification_log = self._classification_log[-200:]

        if necessity_score > 0:
            ctx.relevance_score = min(1.0, ctx.relevance_score + necessity_score * 0.05)

        elif redundant > 0:
            ctx.relevance_score = max(0.0, ctx.relevance_score - 0.05)

        return contexts
