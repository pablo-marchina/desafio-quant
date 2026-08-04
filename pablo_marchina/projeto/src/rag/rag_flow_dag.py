"""RAG flow DAG

Hypothesis: Evaluate whether RAG flow DAG improves final product output without paid dependency.
Category: 8.47 Tool/Flow/Prompt Governance
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RagFlowDag:
    """RAG flow DAG"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_flow_nodes", None):
            self._flow_nodes: list[dict] = []

        for ctx in contexts:
            self._flow_nodes.append(
                {
                    "node": ctx.chunk_id,
                    "stage": kwargs.get("stage", "unknown"),
                    "score": ctx.relevance_score,
                }
            )

        self._flow_nodes = self._flow_nodes[-500:]

        return contexts
