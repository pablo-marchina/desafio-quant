"""experiment manifest

Hypothesis: Evaluate whether experiment manifest improves final product output without paid dependency.
Category: 8.52 Local Experiment Tracking and Benchmark Registry
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ExperimentManifest:
    """experiment manifest"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_experiments", None):
            self._experiments: list[dict] = []

        manifest = {
            "run_params": {k: str(v) for k, v in kwargs.items()},
            "num_contexts": len(contexts),
            "avg_score": sum(c.relevance_score for c in contexts) / max(len(contexts), 1),
        }

        self._experiments.append(manifest)

        self._experiments = self._experiments[-50:]

        return contexts
