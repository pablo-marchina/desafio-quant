"""Contratos de persistência usados pelo módulo de scraping.

O domínio define quais operações precisa, mas não conhece a tecnologia usada
para realizá-las. Mais tarde, a infraestrutura poderá implementar estes
contratos usando memória, PostgreSQL ou outro mecanismo de armazenamento.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from .entities import ScrapingAttempt, ScrapingJob, ScrapingResult
from .enums import ScrapingMethod


class ScrapingJobRepository(ABC):
    """Contrato para salvar e consultar jobs de scraping."""

    @abstractmethod
    async def save(self, job: ScrapingJob) -> None:
        """Cria ou atualiza um job."""

    @abstractmethod
    async def get_by_id(self, job_id: UUID) -> ScrapingJob | None:
        """Retorna o job correspondente ou ``None`` quando ele não existe."""


class ScrapingAttemptRepository(ABC):
    """Contrato para registrar e consultar tentativas de coleta."""

    @abstractmethod
    async def save(self, attempt: ScrapingAttempt) -> None:
        """Cria ou atualiza uma tentativa."""

    @abstractmethod
    async def list_by_job_id(self, job_id: UUID) -> list[ScrapingAttempt]:
        """Retorna todas as tentativas pertencentes a um job."""

    @abstractmethod
    async def count_recent_failures_by_host_and_method(
        self, host: str, method: ScrapingMethod, since: datetime
    ) -> int:
        """Conta tentativas com status FAILED para o host e metodo na janela dada."""


class ScrapingResultRepository(ABC):
    """Contrato para salvar e consultar conteúdos aprovados."""

    @abstractmethod
    async def save(self, result: ScrapingResult) -> None:
        """Salva um resultado aprovado."""

    @abstractmethod
    async def get_by_id(self, result_id: UUID) -> ScrapingResult | None:
        """Retorna o resultado correspondente ou ``None``."""

    @abstractmethod
    async def get_by_content_hash(self, content_hash: str) -> ScrapingResult | None:
        """Procura conteúdo duplicado usando seu hash."""

    @abstractmethod
    async def get_recent_by_url(
        self, url: str, *, since: datetime
    ) -> ScrapingResult | None:
        """Retorna o resultado mais recente para a URL dentro da janela informada."""
