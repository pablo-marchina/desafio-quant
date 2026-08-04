from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class CustomPytestEvals:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._min_relevance = float(config.get("min_relevance", 0.3)) if isinstance(config, dict) else 0.3

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            for ctx in contexts:
                checks = self._run_checks(ctx)

                fail_count = sum(1 for v in checks.values() if not v)

                if fail_count > 0:
                    penalty = 1.0 - (0.2 * fail_count)

                    ctx.relevance_score = round(ctx.relevance_score * max(0.1, penalty), 4)

        return contexts

    @staticmethod
    def _run_checks(ctx: RetrievedContext) -> dict[str, bool]:
        return {
            "has_content": bool(ctx.content.strip()),
            "has_source": bool(ctx.source_id.strip()),
            "has_title": bool(ctx.title.strip()),
            "score_valid": 0.0 <= ctx.relevance_score <= 1.0,
            "content_min_length": len(ctx.content) >= 20,
            "has_product": bool(ctx.product.strip()),
        }
