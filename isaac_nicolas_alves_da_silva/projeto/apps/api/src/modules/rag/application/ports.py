"""Portas que conectam a aplicacao de RAG a tecnologias externas.

A aplicacao precisa de busca lexical e reranking, mas nao deve conhecer
SQL textual contra `chunks` (de `ingestion`) nem o SDK do Cohere
diretamente.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from apps.api.src.modules.rag.application.dto import (
    EvidenceChunkView,
    LexicalSearchResult,
)


class LexicalSearchRepository(ABC):
    """Busca lexical (full-text) sobre o texto dos chunks."""

    @abstractmethod
    async def search(
        self,
        query: str,
        *,
        limit: int,
        source_type: str | None = None,
        document_ids: list[UUID] | None = None,
    ) -> list[LexicalSearchResult]:
        """Busca chunks por relevancia lexical a partir da query."""


class Reranker(ABC):
    """Reordena evidencias recuperadas por relevancia semantica a query."""

    @abstractmethod
    async def rerank(
        self,
        query: str,
        evidences: list[EvidenceChunkView],
        *,
        top_n: int,
    ) -> list[EvidenceChunkView]:
        """Reordena e corta as evidencias para as `top_n` mais relevantes."""


class EmbeddingGenerator(ABC):
    """Gera o vetor de embedding de um texto de consulta.

    Porta interna de `rag` — a implementacao concreta embrulha o contrato
    publico do modulo `embeddings` (`application/public/embedding_service.py`).
    """

    @abstractmethod
    async def generate(self, text: str) -> tuple[float, ...]:
        """Gera o vetor de embedding correspondente ao texto da query."""


class SupplementalEvidenceProvider(ABC):
    """Fornece evidencias curadas complementares ao indice de chunks."""

    @abstractmethod
    async def find(
        self,
        query: str,
        *,
        source_type: str | None = None,
        limit: int,
    ) -> list[EvidenceChunkView]:
        """Busca evidencias suplementares para a consulta."""
