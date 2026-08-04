"""Reranking interface for Hybrid RAG.

Defines an abstract ``Reranker`` with two implementations:
- ``NoOpReranker`` — identity pass-through (fallback when no model available)
- ``OptionalCrossEncoderReranker`` — local cross-encoder via sentence-transformers

No external API calls required.  Cross-encoder is lazy-loaded and
optional.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.rag.schemas import RagEvidenceChunk


class Reranker(ABC):
    """Abstract reranker interface.

    Implementations should be stateless or safely reusable.
    """

    @abstractmethod
    def rerank(
        self,
        query_text: str,
        chunks: list[RagEvidenceChunk],
        top_k: int = 3,
    ) -> list[RagEvidenceChunk]:
        """Rerank chunks by relevance to query_text.

        Parameters
        ----------
        query_text:
            The original query string.
        chunks:
            Chunks to rerank.
        top_k:
            Maximum chunks to return.

        Returns
        -------
        list[RagEvidenceChunk]
            Reranked chunks with score_rerank populated.
        """


class NoOpReranker(Reranker):
    """Identity reranker — preserves input order and scores.

    Used as fallback when no cross-encoder model is available.
    Sets score_rerank = score_fused for each chunk.
    """

    def rerank(
        self,
        query_text: str,
        chunks: list[RagEvidenceChunk],
        top_k: int = 3,
    ) -> list[RagEvidenceChunk]:
        for c in chunks:
            c.score_rerank = c.score_fused
        sorted_chunks = sorted(chunks, key=lambda c: c.score_rerank, reverse=True)
        return sorted_chunks[:top_k]


class OptionalCrossEncoderReranker(Reranker):
    """Cross-encoder reranker using sentence-transformers.

    Lazy-loads the model on first call.  If the model cannot be loaded,
    falls back to NoOpReranker behavior.

    Parameters
    ----------
    model_name:
        Cross-encoder model name (default BAAI/bge-reranker-v2-m3).
    """

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3") -> None:
        self._model_name = model_name
        self._model: Any = None
        self._load_error: str = ""

    def _ensure_model(self) -> bool:
        """Try to load the cross-encoder model.  Returns True on success."""
        if self._model is not None:
            return True
        if self._load_error:
            return False
        try:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self._model_name)
            return True
        except Exception as exc:
            self._load_error = str(exc)
            return False

    @property
    def is_available(self) -> bool:
        """True if the cross-encoder model is loaded or loadable."""
        return self._ensure_model()

    @property
    def load_error(self) -> str:
        """Last model load error message, empty if none."""
        return self._load_error

    def rerank(
        self,
        query_text: str,
        chunks: list[RagEvidenceChunk],
        top_k: int = 3,
    ) -> list[RagEvidenceChunk]:
        if not chunks:
            return []

        if not self._ensure_model():
            # Fallback to NoOp
            fallback = NoOpReranker()
            return fallback.rerank(query_text, chunks, top_k)

        pairs = [(query_text, c.text) for c in chunks]
        try:
            scores = self._model.predict(pairs)  # type: ignore[union-attr]
        except Exception:
            fallback = NoOpReranker()
            return fallback.rerank(query_text, chunks, top_k)

        for chunk, score in zip(chunks, scores, strict=False):
            chunk.score_rerank = round(float(score), 4)

        chunks.sort(key=lambda c: c.score_rerank, reverse=True)
        return chunks[:top_k]


def build_reranker(
    provider: str = "none",
    model_name: str = "BAAI/bge-reranker-v2-m3",
) -> Reranker:
    """Factory: build a Reranker from config string.

    Parameters
    ----------
    provider:
        \"none\" for NoOpReranker, \"local_cross_encoder\" for cross-encoder.
    model_name:
        Cross-encoder model name (ignored when provider=\"none\").

    Returns
    -------
    Reranker
    """
    if provider == "local_cross_encoder":
        return OptionalCrossEncoderReranker(model_name=model_name)
    return NoOpReranker()
