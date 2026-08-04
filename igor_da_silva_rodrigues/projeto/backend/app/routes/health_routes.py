from __future__ import annotations

import os
import requests
from fastapi import APIRouter, Depends, Response, status

from app.persistence.persistence_service import PipelinePersistence
from app.rag.config import RAGConfig
from app.routes.dependencies import get_persistence


router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "nvidia-startup-ai-radar"}


@router.get("/ready")
def ready(
    response: Response,
    persistence: PipelinePersistence = Depends(get_persistence),
) -> dict[str, object]:
    checks: dict[str, bool] = {"supabase": False, "qdrant": False, "searxng": False}
    try:
        persistence.db.table("pipeline_runs").select("id").limit(1).execute()
        checks["supabase"] = True
    except Exception:
        pass
    try:
        checks["qdrant"] = requests.get(RAGConfig.from_env().qdrant_url, timeout=3).ok
    except requests.RequestException:
        pass
    try:
        searxng_url = os.getenv("SEARXNG_BASE_URL", "http://localhost:8080").rstrip("/")
        checks["searxng"] = requests.get(searxng_url, timeout=3).ok
    except requests.RequestException:
        pass
    is_ready = all(checks.values())
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if is_ready else "degraded", "checks": checks}
