"""Testes do health check da API."""

import pytest

from apps.api.src import main


@pytest.mark.anyio
async def test_dependency_health_reports_individual_failures(monkeypatch) -> None:
    """Uma dependencia indisponivel nao deve esconder o estado da outra."""

    async def healthy_postgres() -> bool:
        return True

    async def unavailable_redis() -> bool:
        raise ConnectionError("Redis indisponivel")

    monkeypatch.setattr(main, "check_database_connection", healthy_postgres)
    monkeypatch.setattr(main, "check_redis_connection", unavailable_redis)

    dependencies = await main.get_dependency_health()

    assert dependencies == {
        "postgres": True,
        "redis": False,
    }
