"""Reranker via Cohere Rerank (RAG V4).

Reranking e uma melhoria de qualidade, nao um pre-requisito de
corretude: a busca hibrida (RAG V3) ja funciona sem reranker. Por isso
qualquer falha aqui (API fora, timeout, resposta inesperada) e
capturada e tratada como "sem reranking" - devolve a ordem recebida em
vez de propagar o erro para quem chamou.
"""

import logging

import cohere

from apps.api.src.modules.rag.application.dto import EvidenceChunkView
from apps.api.src.modules.rag.application.ports import Reranker

logger = logging.getLogger(__name__)

DEFAULT_COHERE_RERANK_MODEL = "rerank-v3.5"


class CohereReranker(Reranker):
    """Reordena evidencias usando o endpoint Rerank da Cohere."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_COHERE_RERANK_MODEL,
    ) -> None:
        if not api_key:
            raise ValueError("COHERE_API_KEY e obrigatoria.")

        self._model = model
        self._client = cohere.AsyncClient(api_key)

    async def rerank(
        self,
        query: str,
        evidences: list[EvidenceChunkView],
        *,
        top_n: int,
    ) -> list[EvidenceChunkView]:
        if not evidences:
            return []

        try:
            response = await self._client.rerank(
                model=self._model,
                query=query,
                documents=[evidence.text for evidence in evidences],
                top_n=min(top_n, len(evidences)),
            )
            return [evidences[result.index] for result in response.results]
        except Exception:
            logger.warning(
                "Cohere rerank falhou; mantendo ordem da busca hibrida.",
                exc_info=True,
            )
            return evidences[:top_n]
