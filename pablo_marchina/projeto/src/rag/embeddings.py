"""Embedding provider abstraction for Product RAG.

Supports local (sentence-transformers) for production.
MockEmbeddingProvider is in tests/helpers/mock_embeddings.
"""

from __future__ import annotations

import warnings
from abc import ABC, abstractmethod
from typing import Any
import os

# Backward-compatible import for tests that still import MockEmbeddingProvider
# from this module. New code should import from tests.helpers.mock_embeddings.
try:
    from tests.helpers.mock_embeddings import MockEmbeddingProvider  # noqa: F401

    warnings.warn(
        "Import MockEmbeddingProvider from tests.helpers.mock_embeddings, not src.rag.embeddings",
        DeprecationWarning,
        stacklevel=2,
    )
except ImportError:
    pass


class EmbeddingProvider(ABC):
    """Abstract embedding provider.

    Implementations must be deterministic for the same input text
    when running in the same mode.
    """

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Embed a single text string into a vector."""

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in a single batch call."""


class SentenceTransformerProvider(EmbeddingProvider):
    """Local embedding provider using sentence-transformers.

    Requires the ``sentence-transformers`` package.
    Default model is ``BAAI/bge-m3`` (1024 dimensions, multilingual).
    """

    def __init__(self, model_name: str | None = None) -> None:
        model_name = model_name or os.getenv("RAG_EMBEDDING_MODEL", "BAAI/bge-m3")
        try:
            import sentence_transformers as st
        except ImportError as err:
            raise ImportError(
                "sentence-transformers is required for real RAG embeddings. "
                'Install the optional RAG dependencies with: pip install -e ".[rag]"'
            ) from err

        self.model = st.SentenceTransformer(model_name)
        self._dim = _embedding_dimension(self.model)

    @property
    def vector_size(self) -> int:
        return self._dim

    def embed(self, text: str) -> list[float]:
        result = self.model.encode(text)
        return result.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        result = self.model.encode(texts)
        return result.tolist()


def _embedding_dimension(model: Any) -> int:
    """Return embedding dimension across sentence-transformers versions."""
    get_dimension = getattr(model, "get_embedding_dimension", None)
    if callable(get_dimension):
        dimension = get_dimension()
        if dimension is not None:
            return int(dimension)

    get_legacy_dimension = getattr(model, "get_sentence_embedding_dimension", None)
    if callable(get_legacy_dimension):
        dimension = get_legacy_dimension()
        if dimension is not None:
            return int(dimension)

    return 384
