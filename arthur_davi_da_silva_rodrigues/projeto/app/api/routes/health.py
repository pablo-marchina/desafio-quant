from fastapi import APIRouter

from app.settings import get_settings

router = APIRouter()


@router.get("/health")
def read_health() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "service": settings.app_name, "environment": settings.app_env}
