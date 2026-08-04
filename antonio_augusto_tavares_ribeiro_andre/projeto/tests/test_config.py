"""Testes da config central (F0.3).

Garante defaults seguros, leitura do ambiente (case-insensitive), validação do
reranker, derivações (`sqlalchemy_url`, `langfuse_enabled`) e cache de `get_settings`.
Todos os casos usam `_env_file=None` para não depender de um `.env` local.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.config import Settings, get_settings


def _settings(**env: str) -> Settings:
    # Isola do .env do repo; injeta só o que o teste declara.
    return Settings(_env_file=None, **env)


def test_defaults() -> None:
    s = _settings()
    assert s.reranker_provider == "nemo"
    assert s.output_lang == "pt-BR"  # F0.13
    assert s.nemotron_model_fast.startswith("nvidia/")
    assert s.langfuse_enabled is False  # sem chaves


def test_env_is_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NVIDIA_API_KEY", "nv-123")
    monkeypatch.setenv("OUTPUT_LANG", "en-US")
    s = _settings()
    assert s.nvidia_api_key == "nv-123"
    assert s.output_lang == "en-US"


def test_reranker_provider_validated() -> None:
    assert _settings(reranker_provider="cohere").reranker_provider == "cohere"
    with pytest.raises(ValidationError):
        _settings(reranker_provider="openai")  # fora do Literal


def test_sqlalchemy_url_forces_psycopg_driver() -> None:
    s = _settings(postgres_url="postgresql://u:p@host:5432/db")
    assert s.sqlalchemy_url == "postgresql+psycopg://u:p@host:5432/db"
    # idempotente quando driver já explícito
    s2 = _settings(postgres_url="postgresql+psycopg://u:p@host/db")
    assert s2.sqlalchemy_url == "postgresql+psycopg://u:p@host/db"


def test_langfuse_enabled_requires_both_keys() -> None:
    assert _settings(langfuse_public_key="pk").langfuse_enabled is False
    assert _settings(langfuse_public_key="pk", langfuse_secret_key="sk").langfuse_enabled is True


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()
