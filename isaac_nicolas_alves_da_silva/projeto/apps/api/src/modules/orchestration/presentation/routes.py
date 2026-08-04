"""Rotas HTTP do modulo orchestration."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from apps.api.src.modules.orchestration.application.dto import (
    CreateAnalysisJobInput,
    CreateUrlIngestionJobInput,
    ListUrlIngestionJobsInput,
)
from apps.api.src.modules.orchestration.domain.enums import UrlIngestionJobStatus
from apps.api.src.modules.orchestration.domain.exceptions import (
    AnalysisJobNotFoundError,
    StartupProfileUnavailableError,
    UrlIngestionJobNotFoundError,
    UrlIngestionStillProcessingError,
)
from apps.api.src.modules.orchestration.factories.orchestration_factory import (
    OrchestrationFactory,
)

from .schemas import (
    AnalysisJobResponse,
    CreateAnalysisJobRequest,
    CreateUrlIngestionJobRequest,
    UrlIngestionJobPageResponse,
    UrlIngestionJobResponse,
)

router = APIRouter(
    prefix="/analysis/jobs",
    tags=["orchestration"],
)

url_ingestion_router = APIRouter(
    prefix="/url-ingestion/jobs",
    tags=["orchestration"],
)


@router.post(
    "",
    response_model=AnalysisJobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_analysis_job(body: CreateAnalysisJobRequest) -> AnalysisJobResponse:
    """Executa o pipeline recommendations -> briefing para uma startup."""

    use_case = OrchestrationFactory.create_execute_analysis_job()
    try:
        view = await use_case.execute(
            CreateAnalysisJobInput(startup_id=body.startup_id)
        )
    except StartupProfileUnavailableError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return AnalysisJobResponse.from_view(view)


@router.get("/{analysis_job_id}", response_model=AnalysisJobResponse)
async def get_analysis_job(analysis_job_id: UUID) -> AnalysisJobResponse:
    """Retorna um analysis job por id."""

    use_case = OrchestrationFactory.create_get_analysis_job()
    try:
        view = await use_case.execute(analysis_job_id=analysis_job_id)
    except AnalysisJobNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return AnalysisJobResponse.from_view(view)


@router.get("", response_model=list[AnalysisJobResponse])
async def list_analysis_jobs(startup_id: UUID) -> list[AnalysisJobResponse]:
    """Lista o historico de analysis jobs de uma startup."""

    use_case = OrchestrationFactory.create_list_analysis_jobs()
    views = await use_case.execute(startup_id=startup_id)
    return [AnalysisJobResponse.from_view(view) for view in views]


@url_ingestion_router.post(
    "",
    response_model=UrlIngestionJobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_url_ingestion_job(
    body: CreateUrlIngestionJobRequest,
) -> UrlIngestionJobResponse:
    """Cria uma orquestracao URL -> scraping -> ingestion -> embeddings."""

    use_case = OrchestrationFactory.create_create_url_ingestion_job()
    view = await use_case.execute(
        CreateUrlIngestionJobInput(
            url=body.url,
            source_type=body.source_type,
            startup_id=body.startup_id,
        )
    )
    return UrlIngestionJobResponse.from_view(view)


@url_ingestion_router.get(
    "/{job_id}",
    response_model=UrlIngestionJobResponse,
)
async def get_url_ingestion_job(job_id: UUID) -> UrlIngestionJobResponse:
    """Consulta uma orquestracao URL ingestion por id."""

    use_case = OrchestrationFactory.create_get_url_ingestion_job()
    try:
        view = await use_case.execute(job_id=job_id)
    except UrlIngestionJobNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return UrlIngestionJobResponse.from_view(view)


@url_ingestion_router.get("", response_model=UrlIngestionJobPageResponse)
async def list_url_ingestion_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    job_status: UrlIngestionJobStatus | None = Query(default=None, alias="status"),
    source_type: str | None = None,
) -> UrlIngestionJobPageResponse:
    """Lista o historico global de url ingestion jobs, com filtros."""

    use_case = OrchestrationFactory.create_list_url_ingestion_jobs()
    view = await use_case.execute(
        ListUrlIngestionJobsInput(
            page=page,
            page_size=page_size,
            status=job_status,
            source_type=source_type,
        )
    )
    return UrlIngestionJobPageResponse.from_view(view)


@url_ingestion_router.post(
    "/{job_id}/advance",
    status_code=status.HTTP_202_ACCEPTED,
)
async def advance_url_ingestion_job(job_id: UUID) -> dict[str, str]:
    """Avanca uma etapa da orquestracao URL ingestion."""

    use_case = OrchestrationFactory.create_advance_url_ingestion_job()
    try:
        await use_case.execute(job_id=job_id)
    except UrlIngestionStillProcessingError as error:
        return {"status": "processing", "detail": str(error)}
    except UrlIngestionJobNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"status": "completed"}
