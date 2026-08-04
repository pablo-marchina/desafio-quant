"""Technique runner wrapper for NVIDIA Triton reranking."""
from __future__ import annotations
from typing import Any
from src.rag.schemas import RetrievedContext, RetrievalQuery
from src.rag.triton_reranker import TritonRerankerUnavailable, triton_rerank_contexts

class TritonReranker:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query = kwargs.get("query")
        if not isinstance(query, RetrievalQuery):
            return contexts
        try:
            reranked, _ = triton_rerank_contexts(contexts, query)
            return reranked
        except TritonRerankerUnavailable:
            raise
