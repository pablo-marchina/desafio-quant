"""Testes da factory do CallbackHandler do Langfuse (shared/observability)."""

from types import SimpleNamespace

from apps.api.src.shared.observability import langfuse_handler as handler_module
from apps.api.src.shared.observability.langfuse_handler import get_langfuse_callbacks


def _fake_settings(
    *, langfuse_public_key: str, langfuse_secret_key: str, langfuse_host: str = ""
) -> SimpleNamespace:
    return SimpleNamespace(
        langfuse_public_key=langfuse_public_key,
        langfuse_secret_key=langfuse_secret_key,
        langfuse_host=langfuse_host,
    )


def _reset_export_flag(monkeypatch) -> None:
    monkeypatch.setattr(handler_module, "_env_exported", False)


def test_get_langfuse_callbacks_returns_empty_list_without_keys(monkeypatch) -> None:
    _reset_export_flag(monkeypatch)
    monkeypatch.setattr(
        handler_module,
        "get_settings",
        lambda: _fake_settings(langfuse_public_key="", langfuse_secret_key=""),
    )

    assert get_langfuse_callbacks() == []


def test_get_langfuse_callbacks_returns_handler_when_configured(monkeypatch) -> None:
    _reset_export_flag(monkeypatch)
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)
    monkeypatch.setattr(
        handler_module,
        "get_settings",
        lambda: _fake_settings(
            langfuse_public_key="pk-lf-test",
            langfuse_secret_key="sk-lf-test",
            langfuse_host="http://127.0.0.1:3300",
        ),
    )

    callbacks = get_langfuse_callbacks()

    assert len(callbacks) == 1
    import os

    assert os.environ["LANGFUSE_PUBLIC_KEY"] == "pk-lf-test"
    assert os.environ["LANGFUSE_HOST"] == "http://127.0.0.1:3300"
