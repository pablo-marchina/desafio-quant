"""Testes do bootstrap de tracing Langfuse (F0.8).

Cobrem o caminho **desligado** (CI/local sem chaves — tudo no-op) e o **ligado**
(cliente e callback construídos), além do carimbo de `prompt_version`/`run_id`/`node`
no `traced_config`. Nenhum teste depende de um Langfuse no ar (construção é offline).
"""

from __future__ import annotations

import pytest

from packages.config import get_settings
from packages.observability import tracing
from packages.observability.cost import BUDGET_GUARD, USAGE_RECORDER
from packages.observability.tracing import (
    flush_tracing,
    get_callback_handler,
    get_langfuse,
    langfuse_callbacks,
    traced_config,
)


@pytest.fixture(autouse=True)
def _clear_caches():
    # Cada teste relê settings/cliente do zero (ambos são lru_cache).
    get_settings.cache_clear()
    get_langfuse.cache_clear()
    yield
    get_settings.cache_clear()
    get_langfuse.cache_clear()


def _disable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    # Settings também lê .env; força o caminho desligado independentemente do ambiente.
    monkeypatch.setattr(get_settings(), "langfuse_public_key", "", raising=False)


def test_disabled_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tracing, "get_langfuse", lambda: None)
    assert get_callback_handler() is None
    assert langfuse_callbacks() == []
    flush_tracing()  # não levanta


def test_traced_config_stamps_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tracing, "get_langfuse", lambda: None)
    cfg = traced_config(node="extractor", prompt_version="extractor@v3", run_id="run-1")
    # Langfuse off → sem handler do Langfuse, mas o medidor (F2.9) e a guarda de orçamento
    # (F2.11) acompanham sempre (inócuos offline).
    assert cfg["callbacks"] == [USAGE_RECORDER, BUDGET_GUARD]
    assert cfg["run_name"] == "extractor"
    assert cfg["metadata"]["prompt_version"] == "extractor@v3"
    assert cfg["metadata"]["run_id"] == "run-1"
    assert "extractor" in cfg["metadata"]["langfuse_tags"]


def test_traced_config_carries_usage_recorder_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    # Mesmo com Langfuse ligado, o medidor (F2.9) acompanha junto do handler.
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    get_settings.cache_clear()
    get_langfuse.cache_clear()
    cfg = traced_config(node="classifier")
    assert USAGE_RECORDER in cfg["callbacks"]
    assert BUDGET_GUARD in cfg["callbacks"]
    assert len(cfg["callbacks"]) == 3  # medidor + guarda de orçamento + handler do Langfuse


def test_extra_metadata_passes_through(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tracing, "get_langfuse", lambda: None)
    cfg = traced_config(node="classifier", company="Acme")
    assert cfg["metadata"]["company"] == "Acme"


def test_enabled_builds_client_and_callback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    get_settings.cache_clear()
    get_langfuse.cache_clear()

    assert get_settings().langfuse_enabled is True
    client = get_langfuse()
    assert client is not None
    assert get_callback_handler() is not None
    assert len(langfuse_callbacks()) == 1
