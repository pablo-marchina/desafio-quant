"""Implementação PostgreSQL do contrato ``ScrapingAttemptRepository``."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.modules.scraping.domain.entities import ScrapingAttempt
from apps.api.src.modules.scraping.domain.enums import AttemptStatus, ScrapingMethod
from apps.api.src.modules.scraping.domain.repositories import (
    ScrapingAttemptRepository,
)
from apps.api.src.modules.scraping.infrastructure.database.mappers.scraping_attempt_mapper import (
    ScrapingAttemptMapper,
)
from apps.api.src.modules.scraping.infrastructure.database.models import (
    ScrapingAttemptModel,
)
from apps.api.src.modules.scraping.infrastructure.database.models.scraping_job_model import (
    ScrapingJobModel,
)


class PostgresScrapingAttemptRepository(ScrapingAttemptRepository):
    """Persiste e consulta tentativas usando SQLAlchemy assíncrono."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, attempt: ScrapingAttempt) -> None:
        """Insere uma tentativa nova ou atualiza seu estado."""

        model = await self.session.get(ScrapingAttemptModel, attempt.id)

        if model is None:
            self.session.add(ScrapingAttemptMapper.to_model(attempt))
        else:
            ScrapingAttemptMapper.update_model(model, attempt)

        await self.session.flush()

    async def list_by_job_id(self, job_id: UUID) -> list[ScrapingAttempt]:
        """Lista as tentativas de um job na ordem em que começaram."""

        result = await self.session.scalars(
            select(ScrapingAttemptModel)
            .where(ScrapingAttemptModel.job_id == job_id)
            .order_by(ScrapingAttemptModel.started_at.asc())
        )

        return [
            ScrapingAttemptMapper.to_entity(model)
            for model in result.all()
        ]

    async def count_recent_failures_by_host_and_method(
        self, host: str, method: ScrapingMethod, since: datetime
    ) -> int:
        """Conta falhas recentes de uma estrategia para um host especifico."""

        # Extrai o host da URL via regexp do Postgres para evitar JOIN em tabela
        # auxiliar: captura tudo entre '://' e o primeiro '/', '?', '#' ou ':'.
        host_expr = func.regexp_replace(
            ScrapingJobModel.url,
            r"^https?://([^/?#:]+).*$",
            r"\1",
        )
        stmt = (
            select(func.count())
            .select_from(ScrapingAttemptModel)
            .join(ScrapingJobModel, ScrapingAttemptModel.job_id == ScrapingJobModel.id)
            .where(
                host_expr == host,
                ScrapingAttemptModel.method == method.value,
                ScrapingAttemptModel.status == AttemptStatus.FAILED.value,
                ScrapingAttemptModel.started_at >= since,
            )
        )
        count = await self.session.scalar(stmt)
        return count or 0
