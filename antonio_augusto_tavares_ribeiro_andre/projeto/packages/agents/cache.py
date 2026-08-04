"""Cache de inferência LLM por prompt+modelo+versão (F2.14).

Cacheia a **saída crua** dos nós LLM (search_planner/F2.3, extractor/F2.5, classifier/F2.6)
para dois fins:

- **custo**: os créditos grátis do `build.nvidia.com` têm rate limit; um hit não chega à
  rede (complementa a guarda de orçamento F2.11 — que barra o excesso, enquanto o cache
  evita repetir o que já se gastou);
- **reprodutibilidade**: runs/eval (F7) repetem a mesma entrada e recebem a mesma saída,
  pinando o resultado mesmo no caminho `reason` (temperatura > 0).

**Chave** = digest de `(version_tag, content_sha, perfil, model_id, mensagens)` (`cache_key`):
a versão do prompt e o **hash do corpo** (`Prompt.content_sha`, F0.12) entram na chave, então
o cache **invalida sozinho** quando o prompt muda ou a versão sobe; o `model_id` resolvido do
settings invalida numa troca de modelo; as mensagens (system + turno do usuário) separam
consultas distintas. O `run_id` **não** entra — é exatamente o cross-run que queremos casar.

Só cacheia **inferência determinística** (LLM/embeddings); **scraping nunca** é cacheado aqui
(frescor é responsabilidade do scraper F2.4). Um hit é **grátis**: não dispara os callbacks de
custo/orçamento (F2.9/F2.11), então o trace reflete só o que de fato foi à rede.

**Offline é o default (igual F2.3–F2.13):** o gate `settings.llm_cache_enabled` nasce **off** →
`cache_from_settings` devolve o `NULL_CACHE` (sempre miss, set no-op) e o caminho fica idêntico
ao de antes (e os nós LLM nem rodam na espinha offline, M2/DoD). Backends locais plugáveis:
**disco** (default) ou **Redis** (opt-in); o Redis degrada para disco se a lib/broker faltar, e
get/set são **best-effort** — o cache nunca derruba um run (mesmo ethos do publisher F2.10).
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from packages.config import get_settings

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .prompts import Prompt


# --- chave ---------------------------------------------------------------------


def _msg_type(message: Any) -> str:
    """Tipo da mensagem (`system`/`human`/…), por duck typing (sem importar langchain)."""
    return str(getattr(message, "type", None) or message.__class__.__name__)


def _msg_content(message: Any) -> str:
    """Conteúdo textual da mensagem (idem)."""
    return str(getattr(message, "content", message))


def _model_id_for(profile: str) -> str:
    """Id do modelo resolvido do settings (F0.3) p/ o perfil do prompt (`fast`/`reason`)."""
    s = get_settings()
    return s.nemotron_model_fast if profile == "fast" else s.nemotron_model_reason


def cache_key(prompt: Prompt, messages: Sequence[Any], *, model_id: str | None = None) -> str:
    """Chave estável de cache p/ uma chamada LLM (F2.14).

    Inclui a **versão** e o **hash do corpo** do prompt (`content_sha`, F0.12 → invalida
    quando o prompt muda), o `model_id` (invalida numa troca de modelo) e as **mensagens**
    (separam consultas). Não inclui `run_id` (queremos casar entre runs). `model_id` pode ser
    passado p/ teste puro; senão resolve do settings.
    """
    payload = {
        "version": prompt.version_tag,
        "sha": prompt.content_sha,
        "profile": prompt.model,
        "model": model_id if model_id is not None else _model_id_for(prompt.model),
        "messages": [[_msg_type(m), _msg_content(m)] for m in messages],
    }
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# --- backends ------------------------------------------------------------------


@runtime_checkable
class LLMCache(Protocol):
    """Store de cache: `get` devolve o texto (ou `None` no miss); `set` grava best-effort."""

    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str) -> None: ...


class NullCache:
    """Cache desligado: sempre miss, set no-op (default quando o gate está off)."""

    def get(self, key: str) -> str | None:  # noqa: ARG002
        return None

    def set(self, key: str, value: str) -> None:  # noqa: ARG002
        return None


#: Singleton do cache desligado (default da espinha offline, M2/DoD).
NULL_CACHE = NullCache()


@dataclass
class MemoryCache:
    """Cache em memória (processo) — útil em teste e dentro de um run."""

    store: dict[str, str] = field(default_factory=dict)

    def get(self, key: str) -> str | None:
        return self.store.get(key)

    def set(self, key: str, value: str) -> None:
        self.store[key] = value


@dataclass
class DiskCache:
    """Cache local em disco: um arquivo JSON por chave (`{value, ts}`). `ttl_seconds=0` = eterno.

    Best-effort: arquivo ausente/corrompido ou erro de I/O = miss / set silencioso — o cache
    nunca derruba o run.
    """

    directory: Path
    ttl_seconds: int = 0

    def _path(self, key: str) -> Path:
        return self.directory / f"{key}.json"

    def get(self, key: str) -> str | None:
        try:
            data = json.loads(self._path(key).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if self.ttl_seconds > 0 and time.time() - float(data.get("ts", 0)) > self.ttl_seconds:
            return None
        value = data.get("value")
        return value if isinstance(value, str) else None

    def set(self, key: str, value: str) -> None:
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            self._path(key).write_text(
                json.dumps({"value": value, "ts": time.time()}, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass  # best-effort — telemetria/otimização, não pode derrubar o run


@dataclass
class RedisCache:
    """Cache em Redis (opt-in): `GET/SET` com prefixo + TTL. Best-effort (engole erro de broker)."""

    client: Any
    prefix: str = "tapi:llmcache:"
    ttl_seconds: int = 0

    def get(self, key: str) -> str | None:
        try:
            raw = self.client.get(self.prefix + key)
        except Exception:  # noqa: BLE001 — broker fora do ar = miss, nunca derruba o run
            return None
        if raw is None:
            return None
        return raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)

    def set(self, key: str, value: str) -> None:
        try:
            self.client.set(self.prefix + key, value, ex=self.ttl_seconds or None)
        except Exception:  # noqa: BLE001 — best-effort
            pass


def _redis_cache(redis_url: str, ttl_seconds: int) -> RedisCache | None:
    """Constrói um `RedisCache` (cliente lazy); `None` se a lib `redis` não estiver instalada."""
    try:
        import redis  # import preguiçoso: o módulo importa offline sem a lib
    except ImportError:
        return None
    return RedisCache(redis.Redis.from_url(redis_url), ttl_seconds=ttl_seconds)


def cache_from_settings() -> LLMCache:
    """Cache configurado pelo settings (F0.3); `NULL_CACHE` quando o gate está off (default).

    Backend `redis` degrada para disco se a lib `redis` faltar — o cache é opcional, então
    nunca falha o boot por causa dele.
    """
    s = get_settings()
    if not s.llm_cache_enabled:
        return NULL_CACHE
    if s.llm_cache_backend == "redis":
        cache = _redis_cache(s.redis_url, s.llm_cache_ttl_seconds)
        if cache is not None:
            return cache
    return DiskCache(Path(s.llm_cache_dir), ttl_seconds=s.llm_cache_ttl_seconds)


# --- helper de chamada ---------------------------------------------------------


#: Re-tentativas extras quando uma chamada LLM estoura o teto (F7.6). O endpoint NIM grátis
#: (build.nvidia.com / integrate.api.nvidia.com) congestiona **por-request** e de forma transiente —
#: uma 2ª/3ª tentativa, com conexão nova, costuma passar (provado ao vivo: 1 timeout + retry →
#: sucesso). Só re-tenta no **timeout** (não em erro de parse/credencial — esses propagam na hora).
#: Pior-caso = (1+N)×teto por chamada, mas só quando de fato estoura; o caso típico não muda.
_LLM_TIMEOUT_RETRIES = 2
_LLM_RETRY_BACKOFF_S = 3.0


def _retryable_timeout_types() -> tuple[type[BaseException], ...]:
    """Exceções de timeout que merecem retry (F7.6): o `LLMTimeout` de **parede** (120s) **e** o
    **read timeout** do cliente HTTP do SDK NVIDIA (~60s, via `requests`; alguns caminhos usam
    `httpx`). O read timeout estoura **antes** do guard de parede e **não** é `LLMTimeout`, então
    sem incluí-lo aqui o nó degradava na 1ª falha sem re-tentar — exatamente o que derrubou a
    extração da rivio.ai (`ReadTimeout: ... read timeout=60` no `integrate.api.nvidia.com`).
    Import preguiçoso: o módulo importa offline sem `requests`/`httpx`.
    """
    from .llm import LLMTimeout

    types: list[type[BaseException]] = [LLMTimeout]
    try:
        from requests.exceptions import Timeout as _RequestsTimeout

        types.append(_RequestsTimeout)
    except Exception:  # noqa: BLE001 — requests ausente (offline) → só o LLMTimeout de parede
        pass
    try:
        from httpx import TimeoutException as _HttpxTimeout

        types.append(_HttpxTimeout)
    except Exception:  # noqa: BLE001 — httpx ausente → idem
        pass
    return tuple(types)


def _invoke_chat(prompt: Prompt, messages: Sequence[Any], config: Any) -> str:
    """Chamada real ao Nemotron (F0.7) + coerção p/ str. Import preguiçoso (offline sem lib).

    A invocação passa pelo teto de tempo de parede (F7.6, `run_with_timeout`). **Re-tenta** os
    timeouts (`_LLM_TIMEOUT_RETRIES`) — tanto o `LLMTimeout` de parede quanto o **read timeout** do
    cliente HTTP (o NIM grátis congestiona por-request; a retry com conexão nova costuma passar).
    Esgotadas as tentativas, propaga e o nó degrada p/ o determinista (o invariante F7.6 segue: a
    falha não trava o run).
    """
    from .llm import get_chat, run_with_timeout

    retryable = _retryable_timeout_types()
    chat = get_chat(prompt.model)
    last: BaseException | None = None
    for attempt in range(_LLM_TIMEOUT_RETRIES + 1):
        try:
            raw = run_with_timeout(lambda: chat.invoke(list(messages), config=config)).content
            return raw if isinstance(raw, str) else str(raw)
        except retryable as exc:
            last = exc
            if attempt < _LLM_TIMEOUT_RETRIES:
                time.sleep(_LLM_RETRY_BACKOFF_S)  # deixa a congestão transiente do NIM aliviar
    raise last  # type: ignore[misc]  # esgotou as tentativas → propaga (nó degrada, F7.6)


def cached_completion(
    prompt: Prompt,
    messages: Sequence[Any],
    *,
    config: Any = None,
    cache: LLMCache | None = None,
    invoke: Any = None,
) -> str:
    """Saída crua do LLM com cache (F2.14): hit → devolve do store; miss → chama e grava.

    Substitui o `get_chat(...).invoke(...).content` dos nós LLM. `cache` default vem do
    settings (`NULL_CACHE` quando off → comportamento idêntico ao de antes). `invoke` é o
    disparo real (injetável em teste). **Falhas propagam** (o caller degrada p/ o determinista)
    e **não** são cacheadas; saída vazia também não é gravada.
    """
    store = cache if cache is not None else cache_from_settings()
    key = cache_key(prompt, messages)
    hit = store.get(key)
    if hit is not None:
        return hit
    text = (invoke or _invoke_chat)(prompt, messages, config)
    if text:
        store.set(key, text)
    return text


__all__ = [
    "cache_key",
    "LLMCache",
    "NullCache",
    "NULL_CACHE",
    "MemoryCache",
    "DiskCache",
    "RedisCache",
    "cache_from_settings",
    "cached_completion",
]
