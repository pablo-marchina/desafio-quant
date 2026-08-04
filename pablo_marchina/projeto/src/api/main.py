from __future__ import annotations

import hmac
import os
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from src.api.product_routes import router as product_router
from src.api.workflow_routes import router as workflow_router
from src.database.session import assert_product_schema_current, get_product_database, initialize_product_database
from src.services.product.capability_registry import CapabilityStatus
from src.services.product.health_executor import get_health_executor
from src.services.product.readiness_service import ProductReadinessService

PROMETHEUS_AVAILABLE: bool
try:
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

_PUBLIC_PATHS = {"/health/live", "/health/ready"}
_INSECURE_PROXY_VALUES = {
    "",
    "change-me",
    "replace-me",
    "replace-with-a-random-value-of-at-least-32-characters",
}


def _is_product_mode() -> bool:
    return os.environ.get("APP_MODE", "product").casefold() == "product"


def _validate_security_configuration() -> None:
    if not _is_product_mode():
        return
    mode = os.environ.get("API_AUTH_MODE", "internal_proxy").casefold()
    if mode != "internal_proxy":
        raise RuntimeError("APP_MODE=product requires API_AUTH_MODE=internal_proxy")
    key = os.environ.get("INTERNAL_PROXY_KEY", "")
    if key in _INSECURE_PROXY_VALUES or len(key) < 32:
        raise RuntimeError("INTERNAL_PROXY_KEY must be a non-default random value with at least 32 characters")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    _validate_security_configuration()
    initialize_product_database()
    yield


_product_mode = _is_product_mode()
app = FastAPI(
    title="NVIDIA Startup AI Radar API",
    description="Product API for persisted startup analysis, recommendations, dossiers, and exports.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None if _product_mode else "/docs",
    redoc_url=None if _product_mode else "/redoc",
    openapi_url=None if _product_mode else "/openapi.json",
)


def _cors_origins() -> list[str]:
    configured = os.environ.get("CORS_ALLOWED_ORIGINS", "").strip()
    app_mode = os.environ.get("APP_MODE", "product").casefold()
    if configured:
        origins = [origin.strip() for origin in configured.split(",") if origin.strip()]
    elif app_mode == "product":
        origins = []
    else:
        origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
    if app_mode == "product" and "*" in origins:
        raise RuntimeError("APP_MODE=product does not allow wildcard CORS origins.")
    return origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_and_request_context(request: Request, call_next) -> Response:
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    started = time.monotonic()

    if _is_product_mode() and request.url.path not in _PUBLIC_PATHS:
        expected = os.environ.get("INTERNAL_PROXY_KEY", "")
        provided = request.headers.get("x-internal-proxy-key", "")
        if not expected or not hmac.compare_digest(provided, expected):
            return JSONResponse(
                {"detail": "Request must pass through the trusted frontend proxy.", "request_id": request_id},
                status_code=401,
                headers={"x-request-id": request_id},
            )

    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    response.headers["x-response-time-ms"] = f"{(time.monotonic() - started) * 1000:.1f}"
    return response


app.include_router(product_router)
app.include_router(workflow_router)


@app.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "live", "service": "nvidia-startup-ai-radar-api"}


@app.get("/health/ready")
async def health_ready() -> JSONResponse:
    executor = get_health_executor()
    executor.invalidate()
    dependency_checks = {
        key: executor.check(key)
        for key in ("product_db", "qdrant", "rag", "triton")
    }
    schema_error = ""
    try:
        assert_product_schema_current(get_product_database().engine)
    except Exception as exc:
        schema_error = str(exc)

    product_report = ProductReadinessService().get_product_readiness()
    dependencies_ready = all(
        result.status == CapabilityStatus.available for result in dependency_checks.values()
    )
    ready = product_report.ready and dependencies_ready and not schema_error
    payload = {
        "status": "ready" if ready else "not_ready",
        "ready": ready,
        "schema": {"ready": not schema_error, "detail": schema_error or "Alembic schema is current"},
        "dependencies": {
            key: {
                "status": result.status.value,
                "detail": result.detail,
                "latency_ms": result.latency_ms,
            }
            for key, result in dependency_checks.items()
        },
        "blocking_missing_config": product_report.blocking_missing_config,
        "user_messages": product_report.user_messages,
    }
    return JSONResponse(payload, status_code=200 if ready else 503)


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> PlainTextResponse:
    if not PROMETHEUS_AVAILABLE:
        return PlainTextResponse("# prometheus_client not installed\n", status_code=200)
    return PlainTextResponse(generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)
