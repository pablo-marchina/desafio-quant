from __future__ import annotations

import time
from uuid import uuid4

from fastapi import Request
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.core.observability import LOGGER


async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    clear_contextvars()
    bind_contextvars(request_id=request_id)
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        LOGGER.error(
            "http_request_failed",
            method=request.method,
            path=request.url.path,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            error=str(exc),
        )
        raise
    response.headers["X-Request-ID"] = request_id
    LOGGER.info(
        "http_request_completed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round((time.perf_counter() - started) * 1000, 2),
    )
    clear_contextvars()
    return response
