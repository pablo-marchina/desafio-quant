"""Caso de uso responsavel por consultar um job e suas tentativas."""

from dataclasses import dataclass
from uuid import UUID

from apps.api.src.modules.scraping.application.unit_of_work import (
    ScrapingUnitOfWorkFactory,
)
from apps.api.src.modules.scraping.domain.entities import ScrapingAttempt, ScrapingJob
from apps.api.src.modules.scraping.domain.exceptions import ScrapingJobNotFoundError


@dataclass(frozen=True)
class ScrapingJobDetails:
    """DTO de leitura que reune o job e seu historico de tentativas."""

    job: ScrapingJob
    attempts: list[ScrapingAttempt]


class GetScrapingJob:
    """Consulta os dados necessarios para acompanhar um job."""

    def __init__(self, unit_of_work_factory: ScrapingUnitOfWorkFactory) -> None:
        self.unit_of_work_factory = unit_of_work_factory

    async def execute(self, job_id: UUID) -> ScrapingJobDetails:
        """Retorna o job e suas tentativas ou informa que ele nao existe."""

        # A consulta tambem abre uma Unit of Work para garantir que job e
        # tentativas sejam lidos usando a mesma sessao do banco de dados.
        async with self.unit_of_work_factory() as unit_of_work:
            job = await unit_of_work.job_repository.get_by_id(job_id)
            if job is None:
                raise ScrapingJobNotFoundError(
                    f"O job de scraping {job_id} nao foi encontrado."
                )

            attempts = await unit_of_work.attempt_repository.list_by_job_id(job_id)

            return ScrapingJobDetails(
                job=job,
                attempts=attempts,
            )
