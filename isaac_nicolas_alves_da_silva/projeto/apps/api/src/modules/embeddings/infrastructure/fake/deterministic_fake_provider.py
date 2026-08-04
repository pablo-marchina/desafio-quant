"""Provider fake deterministico de embeddings.

Implementacao V1 do contrato publico ``EmbeddingService``. Nao chama nenhuma
API externa. Dado o mesmo texto, sempre devolve o mesmo vetor, satisfazendo
o criterio de pronto da V1 ("um chunk consegue gerar um vetor fake estavel
em teste"). Sera substituido por um provider real (Gemini ou Cohere) na V2,
escondido atras do mesmo contrato ``EmbeddingService``.
"""

import hashlib

from apps.api.src.modules.embeddings.application.dto import (
    ChunkEmbeddingView,
    GenerateChunkEmbeddingInput,
)
from apps.api.src.modules.embeddings.application.public.embedding_service import (
    EmbeddingService,
)
from apps.api.src.modules.embeddings.domain.entities import EmbeddingVector

DEFAULT_DIMENSION = 16
MODEL_NAME = "fake-deterministic-v1"


class DeterministicFakeEmbeddingProvider(EmbeddingService):
    """Gera vetores fake estaveis a partir do hash SHA-256 do texto."""

    def __init__(self, *, dimension: int = DEFAULT_DIMENSION) -> None:
        self._dimension = dimension

    async def embed(
        self, embedding_input: GenerateChunkEmbeddingInput
    ) -> ChunkEmbeddingView:
        vector = self._derive_vector(embedding_input.text)
        return ChunkEmbeddingView(
            chunk_id=embedding_input.chunk_id,
            values=vector.values,
            dimension=vector.dimension,
            model_name=vector.model_name,
        )

    def _derive_vector(self, text: str) -> EmbeddingVector:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = tuple(
            (digest[i % len(digest)] / 255.0) * 2.0 - 1.0
            for i in range(self._dimension)
        )
        return EmbeddingVector(
            values=values,
            dimension=self._dimension,
            model_name=MODEL_NAME,
        )
