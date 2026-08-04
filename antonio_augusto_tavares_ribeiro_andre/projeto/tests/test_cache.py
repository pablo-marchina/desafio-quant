"""Testes do cache de inferência LLM por prompt+modelo+versão (F2.14).

Tudo offline/determinista (sem rede/LLM/broker). Exercita:
- `cache_key`: estável p/ a mesma entrada; **invalida** quando a versão do prompt sobe, quando
  o corpo do prompt muda (`content_sha`) e quando o `model_id` troca; separa por mensagens;
  **não** depende do `run_id`;
- backends `MemoryCache`/`DiskCache`/`NullCache`: round-trip, miss em chave ausente, arquivo
  corrompido → miss, expiração por TTL, best-effort sem derrubar;
- `cache_from_settings`: off por default → `NULL_CACHE`; ligado → `DiskCache` no dir do settings;
  backend `redis` sem a lib instalada **degrada** p/ disco;
- `cached_completion`: miss chama o `invoke` injetado e grava; hit **não** chama de novo; saída
  vazia não é cacheada; falha propaga e não é gravada; com cache desligado chama sempre.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.agents import cache as cache_mod
from packages.agents.cache import (
    NULL_CACHE,
    DiskCache,
    MemoryCache,
    NullCache,
    RedisCache,
    _redis_cache,
    cache_from_settings,
    cache_key,
    cached_completion,
)
from packages.agents.prompts import Prompt
from packages.config import get_settings


def _prompt(version: str = "v1", *, model: str = "fast", template: str = "CORPO") -> Prompt:
    return Prompt(
        node="search_planner",
        version=version,
        model=model,  # type: ignore[arg-type]
        reasoning=False,
        output_lang="pt-BR",
        template=template,
    )


def _msgs(*contents: str) -> list[SimpleNamespace]:
    """Mensagens fake (duck typing por `.type`/`.content`, sem importar langchain)."""
    return [SimpleNamespace(type="human", content=c) for c in contents]


@pytest.fixture(autouse=True)
def _clear_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# --- cache_key ----------------------------------------------------------------


def test_cache_key_stable_for_same_input() -> None:
    p, msgs = _prompt(), _msgs("acme")
    assert cache_key(p, msgs, model_id="m") == cache_key(p, msgs, model_id="m")


def test_cache_key_invalidates_on_version_bump() -> None:
    msgs = _msgs("acme")
    # mesmo corpo, versão diferente → chave diferente (DoD: invalida quando prompt_version muda).
    assert cache_key(_prompt("v1"), msgs, model_id="m") != cache_key(
        _prompt("v2"), msgs, model_id="m"
    )


def test_cache_key_invalidates_on_body_change() -> None:
    msgs = _msgs("acme")
    assert cache_key(_prompt(template="A"), msgs, model_id="m") != cache_key(
        _prompt(template="B"), msgs, model_id="m"
    )


def test_cache_key_invalidates_on_model_change() -> None:
    p, msgs = _prompt(), _msgs("acme")
    assert cache_key(p, msgs, model_id="m1") != cache_key(p, msgs, model_id="m2")


def test_cache_key_separates_messages() -> None:
    p = _prompt()
    assert cache_key(p, _msgs("acme"), model_id="m") != cache_key(p, _msgs("globo"), model_id="m")


def test_cache_key_resolves_model_from_settings_when_omitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NEMOTRON_MODEL_FAST", "vendor/model-x")
    get_settings.cache_clear()
    p, msgs = _prompt(model="fast"), _msgs("acme")
    assert cache_key(p, msgs) == cache_key(p, msgs, model_id="vendor/model-x")


# --- backends -----------------------------------------------------------------


def test_memory_cache_round_trip() -> None:
    cache = MemoryCache()
    assert cache.get("k") is None
    cache.set("k", "v")
    assert cache.get("k") == "v"


def test_null_cache_is_always_miss() -> None:
    NULL_CACHE.set("k", "v")  # no-op
    assert NULL_CACHE.get("k") is None
    assert isinstance(NULL_CACHE, NullCache)


def test_disk_cache_round_trip(tmp_path: Path) -> None:
    cache = DiskCache(tmp_path / "llm")
    assert cache.get("k") is None  # dir nem existe ainda → miss limpo
    cache.set("k", "valor")
    assert cache.get("k") == "valor"


def test_disk_cache_corrupt_file_is_miss(tmp_path: Path) -> None:
    cache = DiskCache(tmp_path)
    (tmp_path / "k.json").write_text("{not json", encoding="utf-8")
    assert cache.get("k") is None


def test_disk_cache_ttl_expires(tmp_path: Path) -> None:
    cache = DiskCache(tmp_path, ttl_seconds=60)
    cache.set("k", "v")
    assert cache.get("k") == "v"  # fresco
    # reescreve com timestamp velho → expirado.
    import json

    (tmp_path / "k.json").write_text(json.dumps({"value": "v", "ts": 0}), encoding="utf-8")
    assert cache.get("k") is None


# --- cache_from_settings ------------------------------------------------------


def test_cache_from_settings_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_CACHE_ENABLED", raising=False)
    get_settings.cache_clear()
    assert cache_from_settings() is NULL_CACHE


def test_cache_from_settings_disk_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_CACHE_ENABLED", "true")
    monkeypatch.setenv("LLM_CACHE_DIR", "/tmp/tapi-cache")
    get_settings.cache_clear()
    cache = cache_from_settings()
    assert isinstance(cache, DiskCache)
    assert cache.directory == Path("/tmp/tapi-cache")


def test_cache_from_settings_redis_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_CACHE_ENABLED", "true")
    monkeypatch.setenv("LLM_CACHE_BACKEND", "redis")
    get_settings.cache_clear()
    sentinel = MemoryCache()
    monkeypatch.setattr(cache_mod, "_redis_cache", lambda *_a, **_k: sentinel)
    assert cache_from_settings() is sentinel


def test_cache_from_settings_redis_degrades_to_disk_when_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Sem a lib `redis` (ou broker) o backend redis degrada p/ disco — nunca falha o boot.
    monkeypatch.setenv("LLM_CACHE_ENABLED", "true")
    monkeypatch.setenv("LLM_CACHE_BACKEND", "redis")
    get_settings.cache_clear()
    monkeypatch.setattr(cache_mod, "_redis_cache", lambda *_a, **_k: None)
    assert isinstance(cache_from_settings(), DiskCache)


def test_redis_cache_none_without_lib(monkeypatch: pytest.MonkeyPatch) -> None:
    # `sys.modules["redis"] = None` faz `import redis` levantar ImportError → degrada p/ None.
    monkeypatch.setitem(sys.modules, "redis", None)
    assert _redis_cache("redis://localhost:6379/0", 0) is None


def test_redis_cache_built_when_lib_present() -> None:
    pytest.importorskip("redis")  # pula se a lib não estiver instalada
    cache = _redis_cache("redis://localhost:6379/0", 5)  # cliente lazy, sem conexão
    assert isinstance(cache, RedisCache)
    assert cache.ttl_seconds == 5


# --- cached_completion --------------------------------------------------------


def test_cached_completion_miss_then_hit_calls_invoke_once() -> None:
    cache, calls = MemoryCache(), [0]

    def invoke(prompt, messages, config):  # noqa: ANN001, ANN202, ARG001
        calls[0] += 1
        return "RESPOSTA"

    p, msgs = _prompt(), _msgs("acme")
    assert cached_completion(p, msgs, cache=cache, invoke=invoke) == "RESPOSTA"
    assert cached_completion(p, msgs, cache=cache, invoke=invoke) == "RESPOSTA"
    assert calls[0] == 1  # 2ª chamada veio do cache (poupa a rede/free tier)


def test_cached_completion_does_not_cache_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    cache, calls = MemoryCache(), [0]

    def invoke(prompt, messages, config):  # noqa: ANN001, ANN202, ARG001
        calls[0] += 1
        return ""

    p, msgs = _prompt(), _msgs("acme")
    assert cached_completion(p, msgs, cache=cache, invoke=invoke) == ""
    assert cached_completion(p, msgs, cache=cache, invoke=invoke) == ""
    assert calls[0] == 2  # vazio não foi gravado → chamou de novo


def test_cached_completion_does_not_cache_on_failure() -> None:
    cache = MemoryCache()

    def invoke(prompt, messages, config):  # noqa: ANN001, ANN202, ARG001
        raise RuntimeError("rede caiu")

    p, msgs = _prompt(), _msgs("acme")
    with pytest.raises(RuntimeError):
        cached_completion(p, msgs, cache=cache, invoke=invoke)
    assert cache.store == {}  # falha propaga (caller degrada) e não é cacheada


def test_cached_completion_disabled_calls_every_time() -> None:
    calls = [0]

    def invoke(prompt, messages, config):  # noqa: ANN001, ANN202, ARG001
        calls[0] += 1
        return "X"

    p, msgs = _prompt(), _msgs("acme")
    cached_completion(p, msgs, cache=NULL_CACHE, invoke=invoke)
    cached_completion(p, msgs, cache=NULL_CACHE, invoke=invoke)
    assert calls[0] == 2  # cache off → sempre chama


# --- retry no timeout do LLM (NIM congestionado, F7.6) ------------------------


def test_invoke_chat_retries_on_timeout_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    # O NIM grátis congestiona por-request; a retry (conexão nova) passa. _invoke_chat re-tenta o
    # LLMTimeout (_LLM_TIMEOUT_RETRIES=2 → 3 tentativas) e devolve o sucesso da 3ª.
    from packages.agents import llm as llm_mod

    monkeypatch.setattr(cache_mod, "_LLM_RETRY_BACKOFF_S", 0.0)  # sem sleep no teste
    monkeypatch.setattr(llm_mod, "get_chat", lambda model: object())  # chat dummy (não é invocado)
    n = {"c": 0}

    def fake_rwt(call, *a, **k):  # noqa: ANN001, ANN002, ANN003, ANN202, ARG001
        n["c"] += 1
        if n["c"] < 3:
            raise llm_mod.LLMTimeout(120.0)
        return SimpleNamespace(content="resposta da 3a tentativa")

    monkeypatch.setattr(llm_mod, "run_with_timeout", fake_rwt)
    out = cache_mod._invoke_chat(_prompt(), _msgs("x"), config=None)
    assert out == "resposta da 3a tentativa"
    assert n["c"] == 3  # 2 timeouts + 1 sucesso


def test_invoke_chat_propagates_after_exhausting_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    # Timeout persistente (endpoint fora) → esgota as tentativas e propaga (o nó degrada, F7.6).
    from packages.agents import llm as llm_mod

    monkeypatch.setattr(cache_mod, "_LLM_RETRY_BACKOFF_S", 0.0)
    monkeypatch.setattr(llm_mod, "get_chat", lambda model: object())
    n = {"c": 0}

    def always_timeout(call, *a, **k):  # noqa: ANN001, ANN002, ANN003, ANN202, ARG001
        n["c"] += 1
        raise llm_mod.LLMTimeout(120.0)

    monkeypatch.setattr(llm_mod, "run_with_timeout", always_timeout)
    with pytest.raises(llm_mod.LLMTimeout):
        cache_mod._invoke_chat(_prompt(), _msgs("x"), config=None)
    assert n["c"] == 3  # 1 + 2 retries, todas timeout


def test_invoke_chat_retries_on_read_timeout_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    # O read timeout do cliente HTTP (~60s) NAO e LLMTimeout, mas tambem e transiente (NIM
    # congestiona por-request) — deve ser re-tentado (diag rivio.ai: ReadTimeout 60s na extracao).
    import requests

    from packages.agents import llm as llm_mod

    monkeypatch.setattr(cache_mod, "_LLM_RETRY_BACKOFF_S", 0.0)
    monkeypatch.setattr(llm_mod, "get_chat", lambda model: object())
    n = {"c": 0}

    def fake_rwt(call, *a, **k):  # noqa: ANN001, ANN002, ANN003, ANN202, ARG001
        n["c"] += 1
        if n["c"] < 3:
            raise requests.exceptions.ReadTimeout("read timeout=60")
        return SimpleNamespace(content="ok apos read timeout")

    monkeypatch.setattr(llm_mod, "run_with_timeout", fake_rwt)
    out = cache_mod._invoke_chat(_prompt(), _msgs("x"), config=None)
    assert out == "ok apos read timeout"
    assert n["c"] == 3  # 2 read timeouts + 1 sucesso
