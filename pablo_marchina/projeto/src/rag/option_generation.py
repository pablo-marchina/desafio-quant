from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class OptionGeneration:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._options: list[dict[str, Any]] = []

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        objective = kwargs.get("objective", "default")
        for ctx in contexts:
            evidence_density = len(ctx.content.split()) / max(len(ctx.content), 1)

            option_score = ctx.relevance_score * 0.6 + min(evidence_density * 5.0, 0.4)

            ctx.relevance_score = round(min(1.0, option_score), 4)

            self._options.append(
                {
                    "option_id": f"{objective}_{ctx.chunk_id}",
                    "score": ctx.relevance_score,
                    "objective": objective,
                }
            )

            self._options = self._options[-500:]
            contexts.sort(key=lambda c: c.relevance_score, reverse=True)
        return contexts
