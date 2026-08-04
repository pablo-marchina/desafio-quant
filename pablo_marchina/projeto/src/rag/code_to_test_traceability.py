"""code-to-test traceability

Hypothesis: Evaluate whether code-to-test traceability improves final product output without paid dependency.
Category: 8.38 Source Acquisition and Freshness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class CodeToTestTraceability:
    """code-to-test traceability"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_code_test_trace", None):
            self._code_test_trace: dict[str, list[str]] = {}

        for ctx in contexts:
            is_code = any(m in ctx.content for m in ["def ", "class ", "import "])

            is_test = "test" in ctx.source_id.lower() or "test_" in ctx.content

            if is_code and is_test:
                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.1)

            if is_code:
                self._code_test_trace[ctx.source_id] = self._code_test_trace.get(ctx.source_id, [])

            if is_test:
                for src_id in list(self._code_test_trace.keys()):
                    self._code_test_trace[src_id].append(ctx.chunk_id)

                    trace_len = len(self._code_test_trace[src_id])

                    ctx.relevance_score = min(1.0, ctx.relevance_score + min(trace_len * 0.01, 0.1))

        return contexts
