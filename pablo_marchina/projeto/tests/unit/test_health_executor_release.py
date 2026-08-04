from __future__ import annotations

from types import SimpleNamespace

from src.services.product.capability_registry import CapabilityStatus
from src.services.product.health_executor import HealthCheckExecutor


def test_unknown_health_check_fails_closed() -> None:
    result = HealthCheckExecutor(cache_ttl=0).check("not_implemented")
    assert result.status == CapabilityStatus.unavailable
    assert "No health check implemented" in result.detail


def test_triton_ready(monkeypatch) -> None:
    monkeypatch.setenv(
        "TRITON_RERANKER_HEALTH_URL",
        "http://triton.test/v2/models/cross_encoder/ready",
    )

    def fake_get(url: str, timeout: float):
        assert url.endswith("/ready")
        assert timeout == 5.0
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr("httpx.get", fake_get)
    result = HealthCheckExecutor(cache_ttl=0).check("triton")
    assert result.status == CapabilityStatus.available


def test_triton_unavailable(monkeypatch) -> None:
    monkeypatch.setenv(
        "TRITON_RERANKER_HEALTH_URL",
        "http://triton.test/v2/models/cross_encoder/ready",
    )

    def fake_get(url: str, timeout: float):
        raise RuntimeError("connection refused")

    monkeypatch.setattr("httpx.get", fake_get)
    result = HealthCheckExecutor(cache_ttl=0).check("triton")
    assert result.status == CapabilityStatus.unavailable
    assert "connection refused" in result.detail
