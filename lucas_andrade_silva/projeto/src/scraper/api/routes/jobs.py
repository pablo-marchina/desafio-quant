from fastapi import APIRouter, HTTPException, status

from scraper.api.dependencies import job_manager
from scraper.api.schemas import JobResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str) -> dict:
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    return job_manager.as_dict(job)

