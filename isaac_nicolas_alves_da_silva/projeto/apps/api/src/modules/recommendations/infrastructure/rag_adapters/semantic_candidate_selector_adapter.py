"""Adaptador que implementa NvidiaSemanticCandidateSelector via busca RAG.

Chama ``rag/application/public/retriever.py`` filtrado por
``source_type="nvidia_knowledge"`` para recuperar chunks de documentacao
NVIDIA semanticamente relevantes ao texto da startup.

Mapeamento chunk -> slug: deterministico pos-retrieval — verifica quais
keywords de cada tecnologia do catalogo aparecem no texto de cada chunk.
Best-effort: qualquer excecao (sem API key, Qdrant indisponivel, query
vazia) devolve ``set()`` em vez de propagar erro.
"""

import re

from apps.api.src.modules.rag.application.dto import SearchEvidenceInput
from apps.api.src.modules.rag.application.public.retriever import Retriever
from apps.api.src.modules.recommendations.application.ports import (
    NvidiaSemanticCandidateSelector,
)

NVIDIA_KNOWLEDGE_SOURCE_TYPE = "nvidia_knowledge"
SEMANTIC_SEARCH_LIMIT = 20


class RagSemanticNvidiaCandidateSelector(NvidiaSemanticCandidateSelector):
    """Implementa ``NvidiaSemanticCandidateSelector`` via busca hibrida RAG."""

    def __init__(self, retriever: Retriever) -> None:
        self._retriever = retriever

    async def select(
        self,
        query: str,
        technology_keywords: dict[str, tuple[str, ...]],
    ) -> set[str]:
        if not query.strip():
            return set()
        try:
            result = await self._retriever.search(
                SearchEvidenceInput(
                    query=query,
                    limit=SEMANTIC_SEARCH_LIMIT,
                    source_type=NVIDIA_KNOWLEDGE_SOURCE_TYPE,
                )
            )
        except Exception:
            return set()

        if not result.results:
            return set()

        relevant_slugs: set[str] = set()
        for chunk in result.results:
            text_lower = chunk.text.lower()
            for slug, keywords in technology_keywords.items():
                if any(
                    bool(re.search(rf"\b{re.escape(kw.lower())}\b", text_lower))
                    for kw in keywords
                ):
                    relevant_slugs.add(slug)

        return relevant_slugs
