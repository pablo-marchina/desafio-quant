"""Implementação PostgreSQL do contrato ``ScrapingResultRepository``."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.modules.scraping.domain.entities import ScrapingResult
from apps.api.src.modules.scraping.domain.exceptions import (
    DuplicateScrapingContentError,
)
from apps.api.src.modules.scraping.domain.repositories import (
    ScrapingResultRepository,
)
from apps.api.src.modules.scraping.infrastructure.database.mappers.scraping_result_mapper import (
    ScrapingResultMapper,
)
from apps.api.src.modules.scraping.infrastructure.database.models import (
    ScrapingResultModel,
)


class PostgresScrapingResultRepository(ScrapingResultRepository):
    """Persiste e consulta resultados aprovados no PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, result: ScrapingResult) -> None:
        """Insere um resultado novo ou atualiza o registro existente."""

        model = await self.session.get(ScrapingResultModel, result.id)

        try:
            # O savepoint isola uma violacao do hash unico. Assim, a transacao
            # externa continua utilizavel para registrar a falha do job.
            async with self.session.begin_nested():
                if model is None:
                    self.session.add(ScrapingResultMapper.to_model(result))
                else:
                    ScrapingResultMapper.update_model(model, result)

                await self.session.flush()
        except IntegrityError as error:
            duplicate = await self.get_by_content_hash(result.content_hash)
            if duplicate is not None and duplicate.id != result.id:
                raise DuplicateScrapingContentError(
                    "O conteudo coletado ja foi persistido pelo resultado "
                    f"{duplicate.id}."
                ) from error

            # Violacoes de outras regras do banco continuam inesperadas.
            raise

    async def get_by_id(self, result_id: UUID) -> ScrapingResult | None:
        """Consulta um resultado pelo identificador primário."""

        model = await self.session.get(ScrapingResultModel, result_id)
        if model is None:
            return None

        return ScrapingResultMapper.to_entity(model)

    async def get_by_content_hash(
        self,
        content_hash: str,
    ) -> ScrapingResult | None:
        """Consulta um resultado que possua o mesmo hash de conteúdo."""

        model = await self.session.scalar(
            select(ScrapingResultModel).where(
                ScrapingResultModel.content_hash == content_hash
            )
        )
        if model is None:
            return None

        return ScrapingResultMapper.to_entity(model)

    async def get_recent_by_url(
        self, url: str, *, since: datetime
    ) -> ScrapingResult | None:
        """Consulta o resultado mais recente para a URL dentro da janela."""

        model = await self.session.scalar(
            select(ScrapingResultModel)
            .where(
                ScrapingResultModel.url == url,
                ScrapingResultModel.created_at >= since,
            )
            .order_by(ScrapingResultModel.created_at.desc())
            .limit(1)
        )
        if model is None:
            return None

        return ScrapingResultMapper.to_entity(model)
