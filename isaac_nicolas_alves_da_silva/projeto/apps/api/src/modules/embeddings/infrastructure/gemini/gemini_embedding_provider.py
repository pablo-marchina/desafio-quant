"""Provider real de embeddings via Gemini (LangChain).

Implementacao V2 do contrato publico ``EmbeddingService``. Chama a API do
Gemini para gerar o vetor de cada chunk. Substitui o
``DeterministicFakeEmbeddingProvider`` (V1) sem que nenhum chamador precise
mudar — ambos implementam o mesmo contrato.
"""

from langchain_core.embeddings import Embeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from apps.api.src.modules.embeddings.application.dto import (
    ChunkEmbeddingView,
    GenerateChunkEmbeddingInput,
)
from apps.api.src.modules.embeddings.application.public.embedding_service import (
    EmbeddingService,
)
from apps.api.src.modules.embeddings.domain.exceptions import EmbeddingGenerationError


class GeminiEmbeddingProvider(EmbeddingService):
    """Gera embeddings reais chamando o Gemini via LangChain."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        embedding_client: Embeddings | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY e obrigatoria.")
        if not model:
            raise ValueError("GEMINI_EMBEDDING_MODEL e obrigatorio.")

        self._model = model
        self._client = embedding_client or GoogleGenerativeAIEmbeddings(
            google_api_key=api_key,
            model=model,
        )

    async def embed(
        self, embedding_input: GenerateChunkEmbeddingInput
    ) -> ChunkEmbeddingView:
        try:
            values = await self._client.aembed_query(embedding_input.text)
        except Exception as error:
            raise EmbeddingGenerationError(
                f"Gemini nao conseguiu gerar o embedding: {error}."
            ) from error

        return ChunkEmbeddingView(
            chunk_id=embedding_input.chunk_id,
            values=tuple(values),
            dimension=len(values),
            model_name=self._model,
        )
