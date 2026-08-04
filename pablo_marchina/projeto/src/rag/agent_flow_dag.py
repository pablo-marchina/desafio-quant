"""agent flow DAG

Hypothesis: Evaluate whether agent flow DAG improves final product output without paid dependency.
Category: 8.49 Formal Agentic Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class AgentFlowDag:
    """agent flow DAG"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_agent_nodes", None):
            self._agent_nodes: list[dict] = []

        for ctx in contexts:
            self._agent_nodes.append(
                {
                    "agent": kwargs.get("agent_name", "unknown"),
                    "chunk": ctx.chunk_id,
                    "score": ctx.relevance_score,
                    "action": kwargs.get("action", "process"),
                }
            )

        self._agent_nodes = self._agent_nodes[-500:]

        return contexts
