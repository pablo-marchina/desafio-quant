"""Adaptador que implementa EmbeddingGenerator usando o contrato publico do embeddings.

Nao importa nada de ``embeddings`` alem de ``application/public/`` (e o DTO
de input exigido pela assinatura de ``EmbeddingService.embed()``) — a
instancia de ``EmbeddingService`` e' construida pela ``EmbeddingsFactory`` e
injetada aqui.
"""

from uuid import uuid4

from apps.api.src.modules.embeddings.application.dto import GenerateChunkEmbeddingInput
from apps.api.src.modules.embeddings.application.public.embedding_service import (
    EmbeddingService,
)
from apps.api.src.modules.rag.application.ports import EmbeddingGenerator
from apps.api.src.modules.rag.domain.exceptions import RagSearchServiceUnavailableError


class EmbeddingsQueryEmbedder(EmbeddingGenerator):

    def __init__(self, embedding_service: EmbeddingService | None) -> None:
        self._embedding_service = embedding_service

    async def generate(self, text: str) -> tuple[float, ...]:
        if self._embedding_service is None:
            raise RagSearchServiceUnavailableError(
                "Servico de embeddings nao configurado (verifique GEMINI_API_KEY)."
            )

        result = await self._embedding_service.embed(
            GenerateChunkEmbeddingInput(chunk_id=uuid4(), text=text)
        )
        return result.values
