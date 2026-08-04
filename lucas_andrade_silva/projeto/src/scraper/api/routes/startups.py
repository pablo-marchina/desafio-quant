from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from scraper.api.dependencies import (
    job_manager,
    pipeline_runner,
    supabase_service,
)
from scraper.api.schemas import (
    JobAccepted,
    StartupCreate,
    StartupListResponse,
    StartupResponse,
    StartupUpdate,
)
from scraper.api.services.startup_service import StartupNotFoundError

router = APIRouter(prefix="/startups", tags=["startups"])


@router.post(
    "",
    response_model=StartupResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_startup(payload: StartupCreate) -> dict:
    startup = supabase_service.create_startup(
        payload.model_dump(exclude_none=True)
    )
    return {"startup": startup}


@router.get("", response_model=StartupListResponse)
def list_startups(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: str | None = None,
    validation_status: str | None = None,
    enrichment_status: str | None = None,
    ai_classification: str | None = None,
    has_nvidia_recommendation: bool = False,
) -> dict:
    items, total = supabase_service.list_startups(
        page=page,
        page_size=page_size,
        search=search,
        validation_status=validation_status,
        enrichment_status=enrichment_status,
        ai_classification=ai_classification,
        has_nvidia_recommendation=has_nvidia_recommendation,
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{startup_id}", response_model=StartupResponse)
def get_startup(startup_id: str) -> dict:
    try:
        startup = supabase_service.get_startup(startup_id)
    except StartupNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Startup not found",
        ) from error
    return {"startup": startup}


@router.patch("/{startup_id}", response_model=StartupResponse)
def update_startup(startup_id: str, payload: StartupUpdate) -> dict:
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one field must be provided",
        )
    try:
        startup = supabase_service.update_startup(startup_id, changes)
    except StartupNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Startup not found",
        ) from error
    return {"startup": startup}


@router.delete(
    "/{startup_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_startup(startup_id: str) -> Response:
    try:
        supabase_service.delete_startup(startup_id)
    except StartupNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Startup not found",
        ) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _candidate_id_or_404(startup_id: str) -> str:
    try:
        return supabase_service.resolve_candidate_id(startup_id)
    except StartupNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Startup not found",
        ) from error


@router.post(
    "/{startup_id}/identity-check",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_identity_check(startup_id: str) -> dict:
    candidate_id = _candidate_id_or_404(startup_id)
    job = job_manager.submit(
        "identity-check",
        startup_id,
        lambda progress: pipeline_runner.identity_check(candidate_id, progress),
    )
    return {"job_id": job.job_id, "status": job.status}


@router.post(
    "/{startup_id}/enrich",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_enrichment(startup_id: str) -> dict:
    candidate_id = _candidate_id_or_404(startup_id)
    job = job_manager.submit(
        "enrich",
        startup_id,
        lambda progress: pipeline_runner.enrich(candidate_id, progress),
    )
    return {"job_id": job.job_id, "status": job.status}


@router.post(
    "/{startup_id}/company-registration",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_company_registration(startup_id: str) -> dict:
    candidate_id = _candidate_id_or_404(startup_id)
    job = job_manager.submit(
        "company-registration",
        startup_id,
        lambda progress: pipeline_runner.company_registration(
            candidate_id, progress
        ),
    )
    return {"job_id": job.job_id, "status": job.status}
