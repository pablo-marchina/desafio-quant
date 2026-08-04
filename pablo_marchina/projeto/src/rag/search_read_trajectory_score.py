"""search-read trajectory score

Hypothesis: Evaluate whether search-read trajectory score improves final product output without paid dependency.
Category: 8.49 Formal Agentic Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SearchReadTrajectoryScore:
    """search-read trajectory score"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_trajectory", None):
            self._trajectory: list[float] = []

        traj_score = sum(c.relevance_score for c in contexts) / max(len(contexts), 1)

        self._trajectory.append(traj_score)

        self._trajectory = self._trajectory[-20:]

        for ctx in contexts:
            if len(self._trajectory) > 1 and self._trajectory[-1] < self._trajectory[-2]:
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.03)

        return contexts
