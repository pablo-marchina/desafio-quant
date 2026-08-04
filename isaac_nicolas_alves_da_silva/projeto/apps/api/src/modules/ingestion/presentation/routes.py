"""Rotas HTTP do módulo de ingestion."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from apps.api.src.modules.ingestion.domain.exceptions import (
    IngestionJobNotFoundError,
)
from apps.api.src.modules.ingestion.factories.ingestion_factory import IngestionFactory

from .schemas import CreateIngestionJobRequest, IngestionJobResponse

router = APIRouter(
    prefix="/ingestion",
    tags=["ingestion"],
)


@router.post(
    "/jobs",
    response_model=IngestionJobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_ingestion_job(
    body: CreateIngestionJobRequest,
) -> IngestionJobResponse:
    """Cria e enfileira um job de ingestion para um scraping_result."""

    from apps.api.src.modules.ingestion.application.dto import CreateIngestionJobInput

    use_case = IngestionFactory.create_create_ingestion_job()
    view = await use_case.execute(
        CreateIngestionJobInput(
            scraping_result_id=body.scraping_result_id,
            source_type=body.source_type,
        )
    )
    return IngestionJobResponse.from_view(view)


@router.get(
    "/jobs/{job_id}",
    response_model=IngestionJobResponse,
)
async def get_ingestion_job(job_id: UUID) -> IngestionJobResponse:
    """Retorna o estado atual de um job de ingestion."""

    use_case = IngestionFactory.create_get_ingestion_job()
    try:
        view = await use_case.execute(job_id=job_id)
    except IngestionJobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return IngestionJobResponse.from_view(view)
