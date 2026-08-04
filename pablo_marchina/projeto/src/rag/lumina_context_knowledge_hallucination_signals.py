from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class LuminaContextKnowledgeHallucinationSignals:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            for ctx in contexts:
                context_signal, knowledge_signal = self._compute_signals(ctx)

                combined = 0.4 * context_signal + 0.6 * knowledge_signal

                ctx.relevance_score = round(ctx.relevance_score * combined, 4)

        return contexts

    @staticmethod
    def _compute_signals(ctx: RetrievedContext) -> tuple[float, float]:
        content = ctx.content.lower()
        has_citation = ctx.url is not None
        has_numbers = any(c.isdigit() for c in ctx.content)
        context_signal = 0.5
        if has_citation:
            context_signal += 0.3
        if has_numbers:
            context_signal += 0.2
        nvidia_terms = {"nvidia", "cuda", "gpu", "tensorrt", "triton", "rapids", "nemollm", "ai enterprise"}
        found_terms = sum(1 for t in nvidia_terms if t in content)
        knowledge_signal = min(1.0, 0.3 + 0.15 * found_terms)
        return min(1.0, context_signal), knowledge_signal
