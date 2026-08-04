from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext


class TokenLevelHallucinationLabels:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            for ctx in contexts:
                tokens = ctx.content.split()

                hallucinated_tokens = 0

                for token in tokens:
                    if self._is_hallucinated_token(token):
                        hallucinated_tokens += 1

                        if hallucinated_tokens > 0:
                            ratio = hallucinated_tokens / max(len(tokens), 1)

                            ctx.relevance_score = round(ctx.relevance_score * (1.0 - 0.5 * min(ratio, 1.0)), 4)

        return contexts

    @staticmethod
    def _is_hallucinated_token(token: str) -> bool:
        cleaned = re.sub(r"[^a-zA-Z]", "", token)
        if not cleaned:
            return False
        if cleaned[0].isupper() and len(cleaned) > 10:
            return True
        if len(cleaned) > 25:
            return True
        if cleaned.lower() in {"coming", "soon", "planned", "expected", "future"}:
            return True
        return False
