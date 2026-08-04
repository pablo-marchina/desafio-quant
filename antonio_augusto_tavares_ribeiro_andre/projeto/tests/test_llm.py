"""Testes do cliente Nemotron (F0.7).

Validam (offline) o mapeamento perfil→modelo (Nano/Super), os defaults de amostragem,
o endpoint self-hosted (NIM) vs. catálogo build.nvidia.com, o toggle de reasoning e o
cache da factory. O smoke real (rede) só roda com `NVIDIA_API_KEY` presente.
"""

from __future__ import annotations

import threading

import pytest
from langchain_nvidia_ai_endpoints import ChatNVIDIA

from packages.agents import cache as cache_mod
from packages.agents import llm as llm_mod
from packages.agents.classifier import heuristic_score, make_aimi
from packages.agents.llm import (
    LLMTimeout,
    get_chat,
    reasoning_system_message,
    request_timeout_seconds,
    run_with_timeout,
    smoke,
)
from packages.agents.prompts import get_prompt
from packages.config import get_settings
from packages.observability.cost import TokenUsage, capture_usage, record_usage
from packages.schemas import StartupProfile


def test_fast_maps_to_nano() -> None:
    s = get_settings()
    c = get_chat("fast")
    assert isinstance(c, ChatNVIDIA)
    assert c.model == s.nemotron_model_fast
    assert "nano" in c.model
    assert c.temperature == 0.0  # greedy p/ roteamento/normalização


def test_reason_maps_to_super() -> None:
    s = get_settings()
    c = get_chat("reason")
    assert c.model == s.nemotron_model_reason
    assert "super" in c.model
    assert c.temperature == pytest.approx(0.6)  # recomendação NVIDIA p/ reasoning


def test_self_hosted_uses_nim_base_url() -> None:
    s = get_settings()
    c = get_chat("fast", self_hosted=True)
    assert str(c.base_url).rstrip("/") == s.nim_base_url.rstrip("/")


def test_catalog_uses_build_endpoint() -> None:
    c = get_chat("reason")
    assert "integrate.api.nvidia.com" in str(c.base_url)


def test_temperature_override() -> None:
    c = get_chat("reason", temperature=0.0)
    assert c.temperature == 0.0


def test_reasoning_system_message() -> None:
    assert reasoning_system_message(True).content == "detailed thinking on"
    assert reasoning_system_message(False).content == "detailed thinking off"


def test_get_chat_is_cached() -> None:
    assert get_chat("fast") is get_chat("fast")
    assert get_chat("fast") is not get_chat("reason")


@pytest.mark.skipif(
    not get_settings().nvidia_api_key,
    reason="smoke real (F0.7) precisa de NVIDIA_API_KEY",
)
def test_smoke_real() -> None:
    out = smoke("fast")
    assert isinstance(out, str) and out.strip()


# --- timeout por chamada de LLM (F7.6) ----------------------------------------


@pytest.fixture
def _clear_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_request_timeout_seconds_default(_clear_settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_REQUEST_TIMEOUT_SECONDS", raising=False)
    get_settings.cache_clear()
    assert request_timeout_seconds() == 120.0  # default de hardening (F7.6)


def test_request_timeout_seconds_from_env(_clear_settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_REQUEST_TIMEOUT_SECONDS", "3.5")
    get_settings.cache_clear()
    assert request_timeout_seconds() == 3.5


def test_llm_timeout_is_exception_subclass() -> None:
    # Subclasse de Exception → os `except Exception` dos nós (F2.5/F2.6/F4.2/F4.4) a capturam,
    # degradando p/ o determinista (mesmo contrato de qualquer falha de LLM).
    assert issubclass(LLMTimeout, Exception)
    err = LLMTimeout(2.0)
    assert err.seconds == 2.0
    assert "2s" in str(err)


def test_run_with_timeout_returns_value() -> None:
    assert run_with_timeout(lambda: 7, seconds=5) == 7


def test_run_with_timeout_zero_runs_inline() -> None:
    # seconds=0 = sem teto: roda inline (sem thread), devolve o valor.
    assert run_with_timeout(lambda: "ok", seconds=0) == "ok"


def test_run_with_timeout_propagates_exception() -> None:
    def _boom():
        raise ValueError("falha real")

    with pytest.raises(ValueError, match="falha real"):
        run_with_timeout(_boom, seconds=5)


def test_run_with_timeout_raises_on_slow_call() -> None:
    started = threading.Event()
    release = threading.Event()

    def _slow():
        started.set()
        release.wait(2.0)  # auto-libera p/ a thread daemon não pendurar além do teste
        return "tarde demais"

    try:
        with pytest.raises(LLMTimeout):
            run_with_timeout(_slow, seconds=0.05)
        assert started.is_set()  # a chamada chegou a iniciar, só não terminou no teto
    finally:
        release.set()


def test_run_with_timeout_propagates_usage_context() -> None:
    # Regressão F2.9/F2.11: o uso registrado DENTRO da thread worker precisa cair no escopo do
    # run (contextvars não atravessam thread sozinhos — o helper copia o contexto).
    with capture_usage() as scope:
        run_with_timeout(
            lambda: record_usage(
                TokenUsage.for_call(model="x", input_tokens=10, output_tokens=5)
            ),
            seconds=5,
        )
        assert scope.total().total_tokens == 15
        assert scope.total().calls == 1


def test_invoke_chat_honors_timeout(_clear_settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_REQUEST_TIMEOUT_SECONDS", "0.05")
    get_settings.cache_clear()
    release = threading.Event()

    class _SlowChat:
        def invoke(self, _messages, config=None):  # noqa: ANN001, ANN202, ARG002
            release.wait(2.0)
            raise AssertionError("não deveria completar dentro do teto")

    monkeypatch.setattr(llm_mod, "get_chat", lambda *_a, **_k: _SlowChat())
    prompt = get_prompt("classifier")
    try:
        with pytest.raises(LLMTimeout):
            cache_mod._invoke_chat(prompt, [], config=None)
    finally:
        release.set()


def test_make_aimi_falls_back_on_llm_timeout() -> None:
    # Um adapter que estoura o teto (LLMTimeout) degrada p/ a heurística — sem alucinar score.
    profile = StartupProfile(nome="Acme AI")

    def _timing_out(_p):  # noqa: ANN001, ANN202
        raise LLMTimeout(0.01)

    assert make_aimi(profile, classify=_timing_out) == heuristic_score(profile)
