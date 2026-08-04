"""Rotas HTTP expostas pelo módulo de scraping."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from apps.api.src.modules.scraping.domain.exceptions import (
    ScrapingJobNotFoundError,
    ScrapingResultNotFoundError,
    TaskDispatchError,
)
from apps.api.src.modules.scraping.factories.scraping_factory import ScrapingFactory

from .schemas import (
    CreateScrapingJobRequest,
    ScrapingAttemptResponse,
    ScrapingJobDetailsResponse,
    ScrapingJobResponse,
    ScrapingResultResponse,
)


router = APIRouter(
    prefix="/scraping",
    tags=["scraping"],
)


@router.post(
    "/jobs",
    response_model=ScrapingJobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_scraping_job(
    request: CreateScrapingJobRequest,
) -> ScrapingJobResponse:
    """Cria e despacha um novo job de scraping."""

    use_case = ScrapingFactory.create_create_scraping_job()
    try:
        job = await use_case.execute(str(request.url))
    except TaskDispatchError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error

    return ScrapingJobResponse.from_entity(job)


@router.get(
    "/jobs/{job_id}",
    response_model=ScrapingJobDetailsResponse,
)
async def get_scraping_job(job_id: UUID) -> ScrapingJobDetailsResponse:
    """Consulta o estado atual e o histórico de tentativas de um job."""

    use_case = ScrapingFactory.create_get_scraping_job()

    try:
        details = await use_case.execute(job_id)
    except ScrapingJobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return ScrapingJobDetailsResponse(
        job=ScrapingJobResponse.from_entity(details.job),
        attempts=[
            ScrapingAttemptResponse.from_entity(attempt)
            for attempt in details.attempts
        ],
    )


@router.get(
    "/results/{result_id}",
    response_model=ScrapingResultResponse,
)
async def get_scraping_result(result_id: UUID) -> ScrapingResultResponse:
    """Consulta um conteúdo bruto que foi aprovado pela pipeline."""

    use_case = ScrapingFactory.create_get_scraping_result()

    try:
        result = await use_case.execute(result_id)
    except ScrapingResultNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return ScrapingResultResponse.from_entity(result)
