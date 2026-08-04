from fastapi import APIRouter

from app.api.routes import (
    briefings,
    classification,
    diagnostics,
    extraction,
    health,
    knowledge,
    radar,
    recommendations,
    runs,
    startups,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(runs.router, prefix="/runs", tags=["runs"])
api_router.include_router(startups.router, prefix="/startups", tags=["startups"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
api_router.include_router(extraction.router, prefix="/extraction", tags=["extraction"])
api_router.include_router(classification.router, prefix="/classification", tags=["classification"])
api_router.include_router(diagnostics.router, prefix="/diagnostics", tags=["diagnostics"])
api_router.include_router(
    recommendations.router,
    prefix="/recommendations",
    tags=["recommendations"],
)
api_router.include_router(briefings.router, prefix="/briefings", tags=["briefings"])
api_router.include_router(radar.router, prefix="/radar", tags=["radar"])
