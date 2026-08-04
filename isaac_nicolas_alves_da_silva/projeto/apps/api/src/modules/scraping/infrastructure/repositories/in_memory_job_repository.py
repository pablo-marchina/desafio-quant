"""Repositório temporário de jobs armazenados na memória do processo."""

from copy import deepcopy
from uuid import UUID

from apps.api.src.modules.scraping.domain.entities import ScrapingJob
from apps.api.src.modules.scraping.domain.repositories import ScrapingJobRepository


class InMemoryScrapingJobRepository(ScrapingJobRepository):
    """Implementa persistência de jobs sem utilizar banco de dados.

    Este repositório é útil durante o desenvolvimento e em testes. Os dados são
    perdidos quando o processo termina, portanto ele será substituído por uma
    implementação PostgreSQL em produção.
    """

    def __init__(self) -> None:
        # Um dicionário oferece busca direta usando o UUID do job como chave.
        self._jobs: dict[UUID, ScrapingJob] = {}

    async def save(self, job: ScrapingJob) -> None:
        """Cria ou atualiza um job usando seu identificador."""

        # Guardamos uma cópia para simular o isolamento de um banco. Sem isso,
        # alterações posteriores no objeto original mudariam o "registro"
        # armazenado mesmo sem uma nova chamada a save().
        self._jobs[job.id] = deepcopy(job)

    async def get_by_id(self, job_id: UUID) -> ScrapingJob | None:
        """Retorna uma cópia do job ou ``None`` quando ele não existe."""

        job = self._jobs.get(job_id)

        # Também devolvemos uma cópia para impedir que o chamador altere o dado
        # persistido sem chamar save() explicitamente.
        return deepcopy(job) if job is not None else None
