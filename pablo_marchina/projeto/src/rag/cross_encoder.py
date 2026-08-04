from __future__ import annotations

from typing import Any

from src.rag.cross_encoder_reranking import CrossEncoderReranking
from src.rag.schemas import RetrievedContext


class CrossEncoder(CrossEncoderReranking):
    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return super().run(contexts, **kwargs)
