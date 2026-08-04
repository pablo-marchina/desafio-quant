from __future__ import annotations

import logging
import sys
import time
from contextlib import contextmanager
from typing import Any, Iterator

import structlog


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(stream=sys.stdout, level=level, format="%(message)s", force=True)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


configure_logging()
LOGGER = structlog.get_logger("nvidia_startup_ai_radar")


@contextmanager
def logged_stage(stage: str, **context: Any) -> Iterator[dict[str, Any]]:
    started = time.perf_counter()
    metrics: dict[str, Any] = {"stage": stage, "tokens_consumidos": 0}
    LOGGER.info("stage_started", stage=stage, **context)
    try:
        yield metrics
    except Exception as exc:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        LOGGER.error("stage_failed", stage=stage, duration_ms=duration_ms, error=str(exc), **context)
        raise
    else:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        metrics["duration_ms"] = duration_ms
        LOGGER.info("stage_completed", **metrics, **context)
