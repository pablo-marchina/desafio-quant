"""detector robustness under label noise

Hypothesis: Evaluate whether detector robustness under label noise improves final product output without paid dependency.
Category: 8.45 Failure Transparency and Completeness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class DetectorRobustnessUnderLabelNoise:
    """detector robustness under label noise"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        noise_levels = self.config.get("noise_levels", [0.0, 0.05, 0.1])
        import random

        noise = random.choice(noise_levels) if noise_levels else 0.0

        for ctx in contexts:
            if random.random() < noise:
                ctx.relevance_score = max(0.0, min(1.0, ctx.relevance_score + random.uniform(-0.2, 0.2)))

        return contexts
