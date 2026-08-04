"""Repositório temporário de resultados aprovados armazenados em memória."""

from copy import deepcopy
from datetime import datetime
from uuid import UUID

from apps.api.src.modules.scraping.domain.entities import ScrapingResult
from apps.api.src.modules.scraping.domain.repositories import (
    ScrapingResultRepository,
)


class InMemoryScrapingResultRepository(ScrapingResultRepository):
    """Implementa persistência e consulta dos resultados aprovados."""

    def __init__(self) -> None:
        # Armazenamento principal: permite consultar diretamente pelo ID.
        self._results: dict[UUID, ScrapingResult] = {}

        # Índice secundário: liga o hash do conteúdo ao ID do resultado.
        self._result_ids_by_hash: dict[str, UUID] = {}

    async def save(self, result: ScrapingResult) -> None:
        """Cria ou atualiza um resultado e seu índice de conteúdo."""

        existing = self._results.get(result.id)

        # Se um resultado existente mudar de hash, removemos o índice antigo
        # para evitar que ele aponte para conteúdo desatualizado.
        if existing is not None and existing.content_hash != result.content_hash:
            self._result_ids_by_hash.pop(existing.content_hash, None)

        self._results[result.id] = deepcopy(result)
        self._result_ids_by_hash[result.content_hash] = result.id

    async def get_by_id(self, result_id: UUID) -> ScrapingResult | None:
        """Retorna uma cópia do resultado identificado pelo UUID."""

        result = self._results.get(result_id)
        return deepcopy(result) if result is not None else None

    async def get_by_content_hash(
        self,
        content_hash: str,
    ) -> ScrapingResult | None:
        """Retorna um resultado que possua exatamente o mesmo conteúdo."""

        result_id = self._result_ids_by_hash.get(content_hash)
        if result_id is None:
            return None

        return deepcopy(self._results[result_id])

    async def get_recent_by_url(
        self, url: str, *, since: datetime
    ) -> ScrapingResult | None:
        """Retorna o resultado mais recente para a URL dentro da janela."""

        candidates = [
            result
            for result in self._results.values()
            if result.url == url and result.created_at >= since
        ]
        if not candidates:
            return None

        latest = max(candidates, key=lambda result: result.created_at)
        return deepcopy(latest)
