"""code inspection RAG

Hypothesis: Evaluate whether code inspection RAG improves final product output without paid dependency.
Category: 8.48 Software V and V
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class CodeInspectionRag:
    """code inspection RAG"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        code_markers = [
            "def ",
            "class ",
            "import ",
            "from ",
            "return ",
            "function ",
            "var ",
            "let ",
            "const ",
            "int ",
            "void ",
        ]

        for ctx in contexts:
            marker_count = sum(1 for m in code_markers if m in ctx.content)

            if marker_count:
                ctx.relevance_score = min(1.0, ctx.relevance_score + marker_count * 0.03)

        return contexts
