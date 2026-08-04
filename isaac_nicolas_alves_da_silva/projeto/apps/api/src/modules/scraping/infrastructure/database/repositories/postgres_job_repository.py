"""Implementação PostgreSQL do contrato ``ScrapingJobRepository``."""

from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.modules.scraping.domain.entities import ScrapingJob
from apps.api.src.modules.scraping.domain.enums import JobStatus
from apps.api.src.modules.scraping.domain.repositories import ScrapingJobRepository
from apps.api.src.modules.scraping.infrastructure.database.mappers.scraping_job_mapper import (
    ScrapingJobMapper,
)
from apps.api.src.modules.scraping.infrastructure.database.models import (
    ScrapingJobModel,
    ScrapingResultModel,
)


class PostgresScrapingJobRepository(ScrapingJobRepository):
    """Persiste jobs usando uma sessão assíncrona do SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        # A sessão representa a unidade de trabalho atual. O repositório não
        # cria nem fecha sessões; essa responsabilidade ficará na factory ou no
        # caso de uso que delimitar a transação.
        self.session = session

    async def save(self, job: ScrapingJob) -> None:
        """Insere um job novo ou atualiza o registro existente."""

        model = await self.session.get(ScrapingJobModel, job.id)

        if model is None:
            self.session.add(ScrapingJobMapper.to_model(job))
        else:
            ScrapingJobMapper.update_model(model, job)

        # Flush envia mudanças para o PostgreSQL dentro da transação atual, mas
        # não executa commit. Isso permite salvar job, attempts e result de
        # forma atômica antes de confirmar tudo junto.
        await self.session.flush()

    async def get_by_id(self, job_id: UUID) -> ScrapingJob | None:
        """Consulta o job e reconstrói seu result_id quando existir."""

        model = await self.session.get(ScrapingJobModel, job_id)
        if model is None:
            return None

        result_id = await self.session.scalar(
            select(ScrapingResultModel.id).where(
                ScrapingResultModel.job_id == job_id
            )
        )
        if result_id is None and model.status == JobStatus.COMPLETED.value:
            result_id = await self.session.scalar(
                select(ScrapingResultModel.id)
                .where(ScrapingResultModel.url == model.url)
                .order_by(desc(ScrapingResultModel.created_at))
                .limit(1)
            )

        return ScrapingJobMapper.to_entity(model, result_id=result_id)
