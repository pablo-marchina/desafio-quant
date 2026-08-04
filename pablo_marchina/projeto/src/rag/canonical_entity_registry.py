"""canonical entity registry

Hypothesis: Evaluate whether canonical entity registry improves final product output without paid dependency.
Category: 8.50 Terminology and Domain Adaptation
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class CanonicalEntityRegistry:
    """canonical entity registry"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_registry", None):
            self._registry: dict[str, str] = {
                "nvidia": "NVIDIA Corporation",
                "openai": "OpenAI, Inc.",
                "google": "Alphabet Inc.",
                "meta": "Meta Platforms, Inc.",
                "microsoft": "Microsoft Corporation",
                "amd": "Advanced Micro Devices, Inc.",
            }

        for ctx in contexts:
            matches = 0

            for alias, _canonical in self._registry.items():
                if alias.lower() in ctx.content.lower():
                    matches += 1

            if matches:
                ctx.relevance_score = min(1.0, ctx.relevance_score + matches * 0.02)

        return contexts
