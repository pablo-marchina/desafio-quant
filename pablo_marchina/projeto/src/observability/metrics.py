from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

PROMETHEUS_AVAILABLE: bool
try:
    from prometheus_client import Counter, Gauge, Histogram

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


class StageLatencyMetric(BaseModel):
    stage: str
    latency_ms: float = Field(ge=0.0)


class RunMetrics(BaseModel):
    latency_by_stage: list[StageLatencyMetric] = Field(default_factory=list)
    error_count: int = Field(default=0, ge=0)
    fallback_count: int = Field(default=0, ge=0)

    @property
    def total_latency_ms(self) -> float:
        return round(sum(metric.latency_ms for metric in self.latency_by_stage), 4)


# Prometheus metrics
_node_latency: Histogram | None = None
_node_errors: Counter | None = None
_active_runs: Gauge | None = None
_node_results: Counter | None = None


def _init_prometheus() -> None:
    global _node_latency, _node_errors, _active_runs, _node_results
    if not PROMETHEUS_AVAILABLE:
        return
    _node_latency = Histogram(
        "graph_node_latency_seconds",
        "Latency per graph node execution",
        labelnames=["node_name", "status"],
        buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
    )
    _node_errors = Counter(
        "graph_node_errors_total",
        "Total node execution errors",
        labelnames=["node_name"],
    )
    _active_runs = Gauge(
        "graph_active_runs",
        "Number of active workflow runs",
    )
    _node_results = Counter(
        "graph_node_results_total",
        "Total node results by status",
        labelnames=["node_name", "status"],
    )


def observe_node(node_name: str, status: str, latency_seconds: float) -> None:
    if _node_latency is None:
        _init_prometheus()
    if _node_latency is not None:
        _node_latency.labels(node_name=node_name, status=status).observe(latency_seconds)
    if _node_results is not None:
        _node_results.labels(node_name=node_name, status=status).inc()
    if status == "failed" and _node_errors is not None:
        _node_errors.labels(node_name=node_name).inc()


def set_active_runs(count: int) -> None:
    if _active_runs is None:
        _init_prometheus()
    if _active_runs is not None:
        _active_runs.set(count)
