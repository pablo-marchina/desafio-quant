"""procedural memory

Hypothesis: Evaluate whether procedural memory improves final product output without paid dependency.
Category: 8.43 Memory and Negative Learning
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ProceduralMemory:
    """procedural memory"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_procedures", None):
            self._procedures: list[str] = []

        trigger_words = {"step", "procedure", "workflow", "pipeline", "method", "process", "guide"}

        for ctx in contexts:
            words = set(w.lower().strip(".,!?;:") for w in ctx.content.split())

            match_count = len(words & trigger_words)

            if match_count:
                ctx.relevance_score = min(1.0, ctx.relevance_score + match_count * 0.03)

        if kwargs.get("procedure"):
            self._procedures.append(str(kwargs["procedure"]))

        return contexts
