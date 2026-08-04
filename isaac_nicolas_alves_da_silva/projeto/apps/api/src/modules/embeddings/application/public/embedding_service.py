"""Contrato publico do modulo embeddings.

Este e o UNICO arquivo do modulo ``embeddings`` que outros modulos (ex: RAG)
podem importar. A implementacao concreta hoje (V1) e um provider fake
deterministico em ``infrastructure/fake/``; em V2 sera substituida por um
provider real (Gemini ou Cohere) sem que os chamadores precisem mudar. A
escolha de qual implementacao usar e feita por
``factories/embeddings_factory.py``.
"""

from abc import ABC, abstractmethod

from apps.api.src.modules.embeddings.application.dto import (
    ChunkEmbeddingView,
    GenerateChunkEmbeddingInput,
)


class EmbeddingService(ABC):
    """Transforma o texto de um chunk em um vetor de embedding."""

    @abstractmethod
    async def embed(
        self, embedding_input: GenerateChunkEmbeddingInput
    ) -> ChunkEmbeddingView:
        """Recebe o texto de um chunk e devolve o vetor de embedding correspondente."""
