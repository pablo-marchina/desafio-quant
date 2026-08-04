"""Contrato publico para leitura do HTML bruto de um resultado de scraping.

Expoe apenas o HTML aprovado (``raw_html``) — informacao estruturada do
ScrapingResult que outros modulos (orchestration) precisam para extrair
links internos reais em vez de chutar paths fixos (P0d).
"""

from abc import ABC, abstractmethod
from uuid import UUID

from apps.api.src.modules.scraping.application.use_cases.get_scraping_result import (
    GetScrapingResult,
)
from apps.api.src.modules.scraping.domain.exceptions import ScrapingResultNotFoundError


class ScrapingResultHtmlReader(ABC):
    """Le o HTML bruto de um resultado aprovado."""

    @abstractmethod
    async def get_html(self, result_id: UUID) -> str | None:
        """Retorna o raw_html do resultado, ou None se nao encontrado."""


class DefaultScrapingResultHtmlReader(ScrapingResultHtmlReader):
    def __init__(self, *, get_scraping_result: GetScrapingResult) -> None:
        self._get_scraping_result = get_scraping_result

    async def get_html(self, result_id: UUID) -> str | None:
        try:
            result = await self._get_scraping_result.execute(result_id)
            return result.raw_html or None
        except ScrapingResultNotFoundError:
            return None
