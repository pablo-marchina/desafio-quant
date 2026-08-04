"""prompt DAG

Hypothesis: Evaluate whether prompt DAG improves final product output without paid dependency.
Category: 8.17 TOON and Context
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class PromptDag:
    """prompt DAG"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_prompt_dag", None):
            self._prompt_dag: dict[str, list[str]] = {}

        for ctx in contexts:
            if ctx.chunk_id not in self._prompt_dag:
                self._prompt_dag[ctx.chunk_id] = []

            for other in contexts:
                if other.chunk_id != ctx.chunk_id:
                    self._prompt_dag[ctx.chunk_id].append(other.chunk_id)

        return contexts
