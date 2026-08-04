"""Prometheus metrics for the scraping module."""

from __future__ import annotations

from typing import Any

from prometheus_client import Counter, Gauge, Histogram

# ── Fetch metrics ────────────────────────────────────────────────────────────

fetches_total: Counter = Counter(
    "scraping_fetches_total",
    "Total HTTP fetches by status",
    labelnames=["status"],
)

fetch_duration_seconds: Histogram = Histogram(
    "scraping_fetch_duration_seconds",
    "HTTP fetch duration in seconds",
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
)

fetch_bytes_total: Counter = Counter(
    "scraping_fetch_bytes_total",
    "Total bytes fetched over HTTP",
)

# ── Cache metrics ────────────────────────────────────────────────────────────

cache_hits_total: Counter = Counter(
    "scraping_cache_hits_total",
    "Number of cache hits",
)

cache_misses_total: Counter = Counter(
    "scraping_cache_misses_total",
    "Number of cache misses",
)

cache_size_bytes: Gauge = Gauge(
    "scraping_cache_size_bytes",
    "Current cache size in bytes",
)

cache_evictions_total: Counter = Counter(
    "scraping_cache_evictions_total",
    "Number of cache evictions",
)

# ── Dedup metrics ────────────────────────────────────────────────────────────

duplicates_detected_total: Counter = Counter(
    "scraping_duplicates_detected_total",
    "Duplicates detected by method",
    labelnames=["method"],
)

fuzzy_index_size: Gauge = Gauge(
    "scraping_fuzzy_index_size",
    "Number of entries in the fuzzy dedup index",
)

# ── Circuit breaker metrics ──────────────────────────────────────────────────

circuit_breaker_trips_total: Counter = Counter(
    "scraping_circuit_breaker_trips_total",
    "Number of times circuit breakers have tripped open",
    labelnames=["domain"],
)

circuit_breaker_state: Gauge = Gauge(
    "scraping_circuit_breaker_state",
    "Current state of circuit breakers (0=closed, 1=open, 2=half-open)",
    labelnames=["domain"],
)

# ── Rate limiter metrics ─────────────────────────────────────────────────────

rate_limit_throttled_total: Counter = Counter(
    "scraping_rate_limit_throttled_total",
    "Number of times requests were throttled by rate limiter",
    labelnames=["domain"],
)

# ── Content quality metrics ──────────────────────────────────────────────────

content_quality_failures_total: Counter = Counter(
    "scraping_content_quality_failures_total",
    "Content quality failures by reason",
    labelnames=["reason"],
)

# ── Collector orchestration metrics ──────────────────────────────────────────

collection_runs_total: Counter = Counter(
    "scraping_collection_runs_total",
    "Total collection runs",
    labelnames=["status"],
)

sources_collected_total: Counter = Counter(
    "scraping_sources_collected_total",
    "Number of sources collected per run",
)

robots_check_total: Counter = Counter(
    "scraping_robots_check_total",
    "Robots.txt checks by result",
    labelnames=["result"],
)

# ── Parse metrics ────────────────────────────────────────────────────────────

parse_duration_seconds: Histogram = Histogram(
    "scraping_parse_duration_seconds",
    "Text extraction duration in seconds",
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
)

parse_failures_total: Counter = Counter(
    "scraping_parse_failures_total",
    "Parse failures by parser",
    labelnames=["parser"],
)


def observe_fetch(status: str, duration: float, bytes_fetched: int = 0) -> None:
    fetches_total.labels(status=status).inc()
    fetch_duration_seconds.observe(duration)
    if bytes_fetched:
        fetch_bytes_total.inc(bytes_fetched)


def observe_cache_hit() -> None:
    cache_hits_total.inc()


def observe_cache_miss() -> None:
    cache_misses_total.inc()


def observe_duplicate(method: str) -> None:
    duplicates_detected_total.labels(method=method).inc()


def observe_circuit_breaker_trip(domain: str) -> None:
    circuit_breaker_trips_total.labels(domain=domain).inc()
    circuit_breaker_state.labels(domain=domain).set(1)


def observe_rate_limit_throttle(domain: str) -> None:
    rate_limit_throttled_total.labels(domain=domain).inc()


def observe_quality_failure(reason: str) -> None:
    content_quality_failures_total.labels(reason=reason).inc()


def observe_collection_run(status: str, source_count: int = 0) -> None:
    collection_runs_total.labels(status=status).inc()
    if source_count:
        sources_collected_total.inc(source_count)


def observe_robots_check(result: str) -> None:
    robots_check_total.labels(result=result).inc()


def observe_parse_duration(parser: str, duration: float) -> None:
    parse_duration_seconds.observe(duration)
    if duration > 5.0:
        parse_failures_total.labels(parser=parser).inc()
