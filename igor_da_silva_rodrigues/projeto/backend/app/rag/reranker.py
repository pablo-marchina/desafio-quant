from __future__ import annotations

import math
import re
import unicodedata
from typing import Protocol

from app.core.schemas import RetrievedChunk


class Reranker(Protocol):
    def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_n: int,
    ) -> list[RetrievedChunk]: ...


class LexicalReranker:
    def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_n: int = 5,
    ) -> list[RetrievedChunk]:
        if not chunks:
            return []
        query_terms = _tokens(query)
        max_retrieval = max(abs(chunk.retrieval_score) for chunk in chunks) or 1.0
        reranked = []

        for chunk in chunks:
            content_terms = _tokens(f"{chunk.content} {chunk.metadata.tecnologia}")
            metadata_terms = _tokens(" ".join(chunk.metadata.dores_relacionadas))
            overlap = len(query_terms & content_terms) / max(1, len(query_terms))
            metadata_overlap = len(query_terms & metadata_terms) / max(1, len(query_terms))
            retrieval = max(0.0, chunk.retrieval_score / max_retrieval)
            score = 0.35 * retrieval + 0.55 * overlap + 0.1 * metadata_overlap
            if not query_terms.intersection(content_terms):
                score *= 0.35
            score = round(score, 6)
            reranked.append(chunk.model_copy(update={"rerank_score": score}))

        return sorted(
            reranked,
            key=lambda item: (item.rerank_score or -math.inf, item.retrieval_score),
            reverse=True,
        )[:top_n]


class BGEReranker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3") -> None:
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise ValueError(
                "Reranker BGE requer a dependência opcional sentence-transformers"
            ) from exc
        self.model = CrossEncoder(model_name)

    def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_n: int = 5,
    ) -> list[RetrievedChunk]:
        if not chunks:
            return []
        scores = self.model.predict([(query, chunk.content) for chunk in chunks])
        reranked = [
            chunk.model_copy(update={"rerank_score": float(score)})
            for chunk, score in zip(chunks, scores, strict=True)
        ]
        return sorted(reranked, key=lambda item: item.rerank_score or -math.inf, reverse=True)[:top_n]


def _tokens(value: str) -> set[str]:
    normalized = "".join(
        char
        for char in unicodedata.normalize("NFKD", value.lower())
        if not unicodedata.combining(char)
    )
    return {token for token in re.findall(r"[a-z0-9-]{3,}", normalized)}
