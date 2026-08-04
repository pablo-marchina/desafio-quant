from fastapi import APIRouter, HTTPException, status

from scraper.api.dependencies import (
    action_report_service,
    competitive_analysis_service,
    job_manager,
    nvidia_recommendation_service,
    supabase_service,
)
from scraper.api.schemas import (
    ActionReportRequest,
    CompetitiveAnalysisRequest,
    JobAccepted,
    NvidiaRecommendationRequest,
)
from scraper.api.services.startup_service import StartupNotFoundError

router = APIRouter(prefix="/startups", tags=["nvidia"])


@router.post(
    "/{startup_id}/nvidia-recommendation",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_nvidia_recommendation(
    startup_id: str, payload: NvidiaRecommendationRequest | None = None
) -> dict:
    try:
        startup = supabase_service.get_startup(startup_id)
    except StartupNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Startup not found",
        ) from error
    job = job_manager.submit(
        "nvidia-recommendation",
        startup_id,
        lambda progress: nvidia_recommendation_service.recommend(
            startup, progress, need=payload.need if payload else None
        ),
    )
    return {"job_id": job.job_id, "status": job.status}


@router.post(
    "/{startup_id}/competitive-analysis",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_competitive_analysis(
    startup_id: str, payload: CompetitiveAnalysisRequest | None = None
) -> dict:
    try:
        startup = supabase_service.get_startup(startup_id)
    except StartupNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Startup not found",
        ) from error
    job = job_manager.submit(
        "competitive-analysis",
        startup_id,
        lambda progress: competitive_analysis_service.analyze(
            startup, progress, question=payload.question if payload else None
        ),
    )
    return {"job_id": job.job_id, "status": job.status}


@router.post(
    "/{startup_id}/action-report",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_action_report(
    startup_id: str, payload: ActionReportRequest | None = None
) -> dict:
    try:
        startup = supabase_service.get_startup(startup_id)
    except StartupNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Startup not found",
        ) from error
    job = job_manager.submit(
        "action-report",
        startup_id,
        lambda progress: action_report_service.generate(
            startup,
            progress,
            objective=payload.objective if payload else None,
            context=payload.context if payload else None,
        ),
    )
    return {"job_id": job.job_id, "status": job.status}
