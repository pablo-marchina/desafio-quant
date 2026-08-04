from app.routes.metrics_routes import _derive_alerts


def test_alerts_detect_stale_worker_backlog_and_provider_failure(monkeypatch):
    monkeypatch.setenv("BACKLOG_ALERT_THRESHOLD", "20")
    metrics = {
        "workers": {"active_leases": 0, "stale_leases": 1},
        "batch_items": {"pending": 25},
        "external_api_requests": {"firecrawl": 10},
        "external_api_failures": {"firecrawl": 8},
    }

    alerts = _derive_alerts(metrics)

    assert alerts == {
        "worker_stale": 1,
        "worker_missing_with_backlog": 1,
        "backlog_high": 1,
        "firecrawl_failure_ratio_high": 1,
    }


def test_alerts_remain_clear_for_healthy_operation():
    alerts = _derive_alerts(
        {
            "workers": {"active_leases": 1, "stale_leases": 0},
            "batch_items": {"pending": 2},
            "external_api_requests": {"firecrawl": 10},
            "external_api_failures": {"firecrawl": 1},
        }
    )

    assert not any(alerts.values())
