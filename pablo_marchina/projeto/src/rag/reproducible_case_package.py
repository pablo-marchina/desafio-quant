"""reproducible case package

Hypothesis: Evaluate whether reproducible case package improves final product output without paid dependency.
Category: 8.20 Release and Delivery
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ReproducibleCasePackage:
    """reproducible case package"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_case_packages", None):
            self._case_packages: list[dict] = []

        pkg = {
            "case_id": kwargs.get("case_id", "unknown"),
            "contexts": len(contexts),
            "avg_score": sum(c.relevance_score for c in contexts) / max(len(contexts), 1),
        }

        self._case_packages.append(pkg)

        self._case_packages = self._case_packages[-50:]

        return contexts
