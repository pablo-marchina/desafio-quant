from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

load_dotenv()

from scraper.api.dependencies import job_manager
from scraper.api.routes import dashboard, jobs, nvidia, startups, technology
from scraper.api.schemas import HealthResponse
from scraper.api.services.startup_service import (
    SupabaseConfigurationError,
)

logging.basicConfig(
    level=os.getenv("API_LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    job_manager.shutdown(wait=False)


app = FastAPI(
    title="Startup AI Radar API",
    version="0.1.0",
    description="API for Supabase startups and asynchronous pipeline jobs.",
    lifespan=lifespan,
)

origins = [
    origin.strip()
    for origin in os.getenv(
        "API_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router)
app.include_router(startups.router)
app.include_router(nvidia.router)
app.include_router(technology.router)
app.include_router(jobs.router)


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "startup-ai-radar-api"}


@app.exception_handler(SupabaseConfigurationError)
async def configuration_error_handler(
    _: Request, error: SupabaseConfigurationError
) -> JSONResponse:
    logger.error("Supabase configuration error: %s", error)
    return JSONResponse(status_code=503, content={"detail": str(error)})


@app.exception_handler(Exception)
async def unhandled_error_handler(_: Request, error: Exception) -> JSONResponse:
    logger.exception("Unhandled API error", exc_info=error)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


def main() -> None:
    uvicorn.run(
        "scraper.api.main:app",
        host=os.getenv("API_HOST", "127.0.0.1"),
        port=int(os.getenv("API_PORT", "8000")),
        reload=os.getenv("API_RELOAD", "").lower() in {"1", "true", "yes"},
    )


if __name__ == "__main__":
    main()
