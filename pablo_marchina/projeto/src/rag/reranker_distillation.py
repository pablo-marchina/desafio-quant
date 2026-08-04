from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RerankerDistillation:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        teacher_scores = kwargs.get("teacher_scores", None)
        if teacher_scores and len(teacher_scores) == len(contexts):
            for ctx, ts in zip(contexts, teacher_scores, strict=True):
                distillation_loss = round(abs(ctx.relevance_score - ts), 4)
                ctx.relevance_score = round((ctx.relevance_score + ts) / 2.0, 4)
                ctx.content = f"[distill:loss={distillation_loss}]\n{ctx.content}"
        else:
            for ctx in contexts:
                ctx.content = f"[distill:no_teacher]\n{ctx.content}"
        return sorted(contexts, key=lambda c: -c.relevance_score)
