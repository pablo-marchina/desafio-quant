from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter
from typing import Any

from src.observability.metrics import RunMetrics, StageLatencyMetric, observe_node
from src.observability.run_events import RunTrace

OTEL_AVAILABLE: bool
try:
    from opentelemetry import trace as otel_trace

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False


class StructuredTracer:
    def __init__(self, run_id: str) -> None:
        self.trace = RunTrace(run_id=run_id)
        self.metrics = RunMetrics()

    def event(self, event_type: str, *, stage: str, payload: dict[str, Any] | None = None) -> None:
        self.trace.add(event_type, stage=stage, payload=payload)

    def timed_stage(self, stage: str) -> _TimedStage:
        return _TimedStage(self, stage)

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "trace": self.trace.model_dump(mode="json"),
            "metrics": self.metrics.model_dump(mode="json"),
            "total_latency_ms": self.metrics.total_latency_ms,
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class _TimedStage:
    def __init__(self, tracer: StructuredTracer, stage: str) -> None:
        self.tracer = tracer
        self.stage = stage
        self.started = 0.0
        self._otel_span: Any = None

    def __enter__(self) -> _TimedStage:
        self.started = perf_counter()
        self.tracer.event("stage_started", stage=self.stage)
        if OTEL_AVAILABLE:
            tracer = otel_trace.get_tracer("nvidia_startup_ai_radar")
            self._otel_span = tracer.start_as_current_span(f"stage.{self.stage}")
            self._otel_span.__enter__()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        latency_s = perf_counter() - self.started
        latency_ms = latency_s * 1000
        self.tracer.metrics.latency_by_stage.append(StageLatencyMetric(stage=self.stage, latency_ms=latency_ms))
        event_type = "stage_failed" if exc is not None else "stage_completed"
        self.tracer.event(event_type, stage=self.stage, payload={"latency_ms": round(latency_ms, 4)})
        status = "failed" if exc is not None else "completed"
        observe_node(self.stage, status, latency_s)
        if self._otel_span is not None:
            if exc is not None:
                self._otel_span.__exit__(type(exc), exc, traceback)
            else:
                self._otel_span.__exit__(None, None, None)
