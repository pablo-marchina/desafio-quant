from __future__ import annotations

import os
from typing import Protocol

from fastembed import SparseTextEmbedding, TextEmbedding
from qdrant_client import models

from app.rag.config import RAGConfig


class DenseEmbeddingProvider(Protocol):
    @property
    def dimension(self) -> int: ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class FastEmbedDenseProvider:
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        self.model = TextEmbedding(model_name=model_name, lazy_load=True)
        self._dimension: int | None = None

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            self._dimension = len(self.embed_query("dimension probe"))
        return self._dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = [vector.tolist() for vector in self.model.embed(texts)]
        if vectors and self._dimension is None:
            self._dimension = len(vectors[0])
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class OpenAIDenseProvider:
    def __init__(self, model_name: str, dimensions: int = 1536) -> None:
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY não configurada")
        from langchain_openai import OpenAIEmbeddings

        self.embeddings = OpenAIEmbeddings(model=model_name, dimensions=dimensions)
        self._dimension = dimensions

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self.embeddings.embed_query(text)


class BM25SparseProvider:
    def __init__(self, model_name: str = "Qdrant/bm25") -> None:
        self.model = SparseTextEmbedding(model_name=model_name, lazy_load=True)

    def embed_documents(self, texts: list[str]) -> list[models.SparseVector]:
        return [
            models.SparseVector(indices=vector.indices.tolist(), values=vector.values.tolist())
            for vector in self.model.embed(texts)
        ]

    def embed_query(self, text: str) -> models.SparseVector:
        return self.embed_documents([text])[0]


def create_dense_provider(config: RAGConfig) -> DenseEmbeddingProvider:
    if config.embedding_provider == "openai":
        return OpenAIDenseProvider(
            model_name=config.embedding_model,
            dimensions=config.openai_embedding_dimensions,
        )
    return FastEmbedDenseProvider(model_name=config.embedding_model)
