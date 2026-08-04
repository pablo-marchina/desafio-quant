from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
import os
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from app.persistence.persistence_service import PipelinePersistence
from app.routes.auth import require_metrics_token
from app.routes.security import enforce_security
from app.routes.dependencies import get_persistence


router = APIRouter(tags=["metrics"])


@router.get("/api/v1/metrics", dependencies=[Depends(enforce_security)])
def metrics_json(
    persistence: PipelinePersistence = Depends(get_persistence),
) -> dict[str, Any]:
    return _collect_dashboard_metrics(persistence)


@router.get(
    "/metrics",
    response_class=PlainTextResponse,
    include_in_schema=False,
    dependencies=[Depends(require_metrics_token)],
)
def metrics_prometheus(
    persistence: PipelinePersistence = Depends(get_persistence),
) -> PlainTextResponse:
    metrics = _collect_metrics(persistence)
    lines = []
    for group, values in metrics.items():
        for label, count in values.items():
            metric = f"nvidia_radar_{group}_total"
            lines.append(f'{metric}{{status="{label}"}} {count}')
    return PlainTextResponse("\n".join(lines) + "\n")


def _collect_metrics(persistence: PipelinePersistence) -> dict[str, dict[str, int | float]]:
    metrics: dict[str, dict[str, int | float]] = {
        "pipeline_runs": _status_counts(persistence, "pipeline_runs"),
        "batch_runs": _status_counts(persistence, "batch_runs"),
        "batch_items": _status_counts(persistence, "batch_items"),
    }
    metrics.update(_worker_metrics(persistence))
    metrics.update(_external_api_metrics(persistence))
    metrics["alerts"] = _derive_alerts(metrics)
    return metrics


def _collect_dashboard_metrics(persistence: PipelinePersistence) -> dict[str, Any]:
    startups = persistence.db.table("startups").select("id").execute().data or []
    runs = (
        persistence.db.table("pipeline_runs")
        .select("id,startup_id,status,duration_ms,created_at")
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )
    status_counts = Counter(str(run.get("status", "unknown")) for run in runs)
    completed_durations = [
        float(run["duration_ms"])
        for run in runs
        if run.get("duration_ms") is not None and run.get("status") == "completed"
    ]
    today = datetime.now(UTC).date()
    runs_today = sum(
        1
        for run in runs
        if (created := _parse_datetime(run.get("created_at"))) is not None
        and created.date() == today
    )

    latest_by_startup: dict[str, dict[str, Any]] = {}
    for run in runs:
        startup_id = run.get("startup_id")
        if startup_id:
            latest_by_startup.setdefault(str(startup_id), run)
    latest_run_ids = [str(run["id"]) for run in latest_by_startup.values()]
    assessments = []
    if latest_run_ids:
        assessments = (
            persistence.db.table("ai_assessments")
            .select("pipeline_run_id,classificacao")
            .in_("pipeline_run_id", latest_run_ids)
            .execute()
            .data
            or []
        )
    maturity_distribution = dict(
        Counter(str(row.get("classificacao", "unknown")) for row in assessments)
    )
    assessed_run_ids = {str(row.get("pipeline_run_id")) for row in assessments}
    maturity_distribution["unknown"] = max(
        len(startups) - len(assessed_run_ids),
        0,
    )

    total_runs = len(runs)
    completed_runs = status_counts.get("completed", 0)
    return {
        "total_startups": len(startups),
        "total_runs": total_runs,
        "completed_runs": completed_runs,
        "failed_runs": status_counts.get("failed", 0),
        "partial_runs": status_counts.get("partial", 0),
        "pending_runs": status_counts.get("pending", 0) + status_counts.get("running", 0),
        "avg_duration_ms": (
            round(sum(completed_durations) / len(completed_durations), 2)
            if completed_durations
            else None
        ),
        "maturity_distribution": maturity_distribution,
        "runs_today": runs_today,
        "success_rate": round(completed_runs / total_runs * 100, 1) if total_runs else 0,
    }


def _status_counts(persistence: PipelinePersistence, table: str) -> dict[str, int | float]:
    response = persistence.db.table(table).select("status").execute()
    return dict(Counter(row["status"] for row in (response.data or [])))


def _worker_metrics(
    persistence: PipelinePersistence,
) -> dict[str, dict[str, int | float]]:
    response = (
        persistence.db.table("batch_runs")
        .select("status,lease_expires_at")
        .eq("status", "running")
        .execute()
    )
    active = list(response.data or [])
    now = datetime.now(UTC)
    stale = 0
    for row in active:
        lease_expires_at = _parse_datetime(row.get("lease_expires_at"))
        if lease_expires_at is None or lease_expires_at <= now:
            stale += 1
    return {"workers": {"active_leases": len(active), "stale_leases": stale}}


def _external_api_metrics(
    persistence: PipelinePersistence,
) -> dict[str, dict[str, int | float]]:
    rpc = getattr(persistence.db, "rpc", None)
    if not callable(rpc):
        return {}
    response = rpc("external_api_metrics", {}).execute()
    requests: dict[str, int | float] = {}
    cache_hits: dict[str, int | float] = {}
    failures: dict[str, int | float] = {}
    costs: dict[str, int | float] = {}
    for row in response.data or []:
        provider = str(row["provider"])
        requests[provider] = int(row.get("requests") or 0)
        cache_hits[provider] = int(row.get("cache_hits") or 0)
        failures[provider] = int(row.get("failures") or 0)
        costs[provider] = round(float(row.get("estimated_cost_usd") or 0), 6)
    return {
        "external_api_requests": requests,
        "external_api_cache_hits": cache_hits,
        "external_api_failures": failures,
        "external_api_estimated_cost_usd": costs,
    }


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _derive_alerts(
    metrics: dict[str, dict[str, int | float]],
) -> dict[str, int | float]:
    workers = metrics.get("workers", {})
    batch_items = metrics.get("batch_items", {})
    requests = metrics.get("external_api_requests", {})
    failures = metrics.get("external_api_failures", {})
    pending = int(batch_items.get("pending", 0))
    backlog_threshold = int(os.getenv("BACKLOG_ALERT_THRESHOLD", "20"))
    firecrawl_requests = int(requests.get("firecrawl", 0))
    firecrawl_failures = int(failures.get("firecrawl", 0))
    return {
        "worker_stale": int(workers.get("stale_leases", 0) > 0),
        "worker_missing_with_backlog": int(
            pending > 0 and workers.get("active_leases", 0) == 0
        ),
        "backlog_high": int(pending >= backlog_threshold),
        "firecrawl_failure_ratio_high": int(
            firecrawl_requests >= 5 and firecrawl_failures / firecrawl_requests >= 0.5
        ),
    }
