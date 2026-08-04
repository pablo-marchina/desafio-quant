"""Servico de aplicacao responsavel por detectar conteudo duplicado."""

from apps.api.src.modules.scraping.domain.entities import ScrapingResult
from apps.api.src.modules.scraping.domain.repositories import ScrapingResultRepository


class ContentDeduplicationService:
    """Consulta resultados persistidos sem depender da tecnologia de banco."""

    def __init__(self, result_repository: ScrapingResultRepository) -> None:
        self.result_repository = result_repository

    async def find_duplicate(
        self,
        result: ScrapingResult,
    ) -> ScrapingResult | None:
        """Retorna o resultado existente com o mesmo hash, quando houver."""

        duplicate = await self.result_repository.get_by_content_hash(
            result.content_hash
        )

        # Salvar novamente o proprio resultado e uma atualizacao, nao uma
        # duplicidade. Por isso comparamos tambem os identificadores.
        if duplicate is not None and duplicate.id == result.id:
            return None

        return duplicate
