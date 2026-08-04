import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.api_middleware import request_context_middleware
from app.routes import analysis_router, auth_router, batch_router, health_router, metrics_router


app = FastAPI(
    title="NVIDIA Startup AI Radar API",
    description="API para investigacao em lote, analise de IA e briefing NVIDIA Inception.",
    version="1.0.0",
)
configured_origins = os.getenv("CORS_ALLOWED_ORIGINS", "")
allowed_origins = [item.strip() for item in configured_origins.split(",") if item.strip()]
if not allowed_origins and os.getenv("ENVIRONMENT", "development").lower() != "production":
    allowed_origins = ["http://localhost:3000", "http://localhost:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)
app.middleware("http")(request_context_middleware)
app.include_router(health_router)
app.include_router(metrics_router)
app.include_router(auth_router)
app.include_router(batch_router)
app.include_router(analysis_router)
