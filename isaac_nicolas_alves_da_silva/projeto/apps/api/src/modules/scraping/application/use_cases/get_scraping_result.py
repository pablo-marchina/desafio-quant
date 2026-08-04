"""Caso de uso responsavel por consultar um resultado aprovado."""

from uuid import UUID

from apps.api.src.modules.scraping.application.unit_of_work import (
    ScrapingUnitOfWorkFactory,
)
from apps.api.src.modules.scraping.domain.entities import ScrapingResult
from apps.api.src.modules.scraping.domain.exceptions import (
    ScrapingResultNotFoundError,
)


class GetScrapingResult:
    """Consulta o conteudo bruto aprovado produzido pela pipeline."""

    def __init__(self, unit_of_work_factory: ScrapingUnitOfWorkFactory) -> None:
        self.unit_of_work_factory = unit_of_work_factory

    async def execute(self, result_id: UUID) -> ScrapingResult:
        """Retorna o resultado identificado ou informa que ele nao existe."""

        # Mesmo consultas simples abrem sua propria Unit of Work. Isso garante
        # que a sessao seja criada e fechada no limite exato da operacao.
        async with self.unit_of_work_factory() as unit_of_work:
            result = await unit_of_work.result_repository.get_by_id(result_id)
            if result is None:
                raise ScrapingResultNotFoundError(
                    f"O resultado de scraping {result_id} nao foi encontrado."
                )

            return result
