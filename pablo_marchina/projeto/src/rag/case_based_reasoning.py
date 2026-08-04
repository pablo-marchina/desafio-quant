from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class CaseBasedReasonerConfig(BaseModel):
    enabled: bool = True
    similarity_threshold: float = 0.3
    max_cases: int = 5


class CaseBasedReasoner:
    def __init__(self, config: Any | None = None) -> None:
        self.config = CaseBasedReasonerConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        target_content = kwargs.get("query", "")
        if not target_content or not contexts:
            return contexts
        target_lower = target_content.lower()
        target_tokens = set(target_lower.split())
        for ctx in contexts:
            ctx_tokens = set(ctx.content.lower().split())
            overlap = len(target_tokens & ctx_tokens)
            union = len(target_tokens | ctx_tokens)
            if union > 0:
                jaccard = overlap / union
                if jaccard >= self.config.similarity_threshold:
                    ctx.relevance_score = round(min(ctx.relevance_score + jaccard * 0.2, 1.0), 4)
        contexts.sort(key=lambda c: c.relevance_score, reverse=True)
        return contexts[: self.config.max_cases]
