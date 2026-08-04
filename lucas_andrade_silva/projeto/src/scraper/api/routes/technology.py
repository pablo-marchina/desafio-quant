from fastapi import APIRouter, HTTPException, status

from scraper.api.dependencies import (
    job_manager,
    supabase_service,
    technology_intelligence_service,
)
from scraper.api.schemas import JobAccepted
from scraper.api.services.startup_service import StartupNotFoundError

router = APIRouter(prefix="/startups", tags=["technology-intelligence"])


@router.post(
    "/{startup_id}/technology-intelligence",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_technology_intelligence(startup_id: str) -> dict:
    try:
        startup = supabase_service.get_startup(startup_id)
    except StartupNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Startup not found",
        ) from error
    job = job_manager.submit(
        "technology-intelligence",
        startup_id,
        lambda progress: technology_intelligence_service.analyze(
            startup, progress
        ),
    )
    return {"job_id": job.job_id, "status": job.status}
