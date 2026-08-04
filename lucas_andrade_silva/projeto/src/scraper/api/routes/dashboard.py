from fastapi import APIRouter

from scraper.api.dependencies import supabase_service
from scraper.api.schemas import DashboardSummaryResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary() -> dict:
    return supabase_service.dashboard_summary()

