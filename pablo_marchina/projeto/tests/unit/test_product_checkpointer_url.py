from __future__ import annotations

from src.orchestration.runner import _postgres_connection_url


def test_checkpointer_prefers_dedicated_postgres_url(monkeypatch) -> None:
    monkeypatch.setenv("APP_MODE", "product")
    monkeypatch.setenv(
        "PRODUCT_DB_URL",
        "postgresql+psycopg2://radar:secret@postgres:5432/nvidia_radar",
    )
    monkeypatch.setenv(
        "LANGGRAPH_POSTGRES_URL",
        "postgresql://checkpoint:secret@postgres:5432/nvidia_radar",
    )

    assert _postgres_connection_url() == (
        "postgresql://checkpoint:secret@postgres:5432/nvidia_radar"
    )


def test_checkpointer_normalizes_sqlalchemy_driver_url(monkeypatch) -> None:
    monkeypatch.setenv("APP_MODE", "product")
    monkeypatch.delenv("LANGGRAPH_POSTGRES_URL", raising=False)
    monkeypatch.setenv(
        "PRODUCT_DB_URL",
        "postgresql+psycopg2://radar:secret@postgres:5432/nvidia_radar",
    )

    assert _postgres_connection_url() == (
        "postgresql://radar:secret@postgres:5432/nvidia_radar"
    )
