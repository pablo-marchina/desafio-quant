"""jargon expansion

Hypothesis: Evaluate whether jargon expansion improves final product output without paid dependency.
Category: 8.50 Terminology and Domain Adaptation
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class JargonExpansion:
    """jargon expansion"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_jargon_map", None):
            self._jargon_map: dict[str, str] = {
                "h100": "NVIDIA H100 Tensor Core GPU",
                "a100": "NVIDIA A100 Tensor Core GPU",
                "triton": "NVIDIA Triton Inference Server",
                "nemotron": "NVIDIA Nemotron",
                "cuda": "NVIDIA CUDA parallel computing platform",
                "tensorrt": "NVIDIA TensorRT inference optimization SDK",
            }

        for ctx in contexts:
            expansion_count = 0

            for jargon, _expanded in self._jargon_map.items():
                if jargon.lower() in ctx.content.lower():
                    expansion_count += 1

            if expansion_count:
                ctx.relevance_score = min(1.0, ctx.relevance_score + expansion_count * 0.03)

        return contexts
