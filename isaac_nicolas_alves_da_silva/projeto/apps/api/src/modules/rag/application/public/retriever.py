"""Contrato publico para recuperar evidencias."""

from abc import ABC, abstractmethod

from apps.api.src.modules.rag.application.dto import (
    SearchEvidenceInput,
    SearchEvidenceView,
)


class Retriever(ABC):
    """Recupera evidencias relevantes para uma pergunta."""

    @abstractmethod
    async def search(self, search_input: SearchEvidenceInput) -> SearchEvidenceView:
        """Busca evidencias citaveis."""
