"""Factory de clientes Nemotron (F0.7).

Dois perfis de modelo, conforme ARQUITETURA §"Modelos Nemotron por tarefa":
- **fast** → **Nano**: `search_planner`, roteamento de scraping, normalização.
- **reason** → **Super**: `extractor`, `classifier`, `recommender`, `briefing`
  (reasoning ligado por system message, ver `reasoning_system_message`).

Consome a config central (F0.3): chave, nomes de modelo e `nim_base_url`. O callback
do Langfuse (F0.8) **não** entra aqui — é passado em tempo de `.invoke(config=...)`
pelos nós (F2), para que o mesmo cliente cacheado sirva runs com traces distintos.
"""

from __future__ import annotations

import contextvars
import threading
from collections.abc import Callable
from functools import lru_cache
from typing import Literal, TypeVar

from langchain_core.messages import SystemMessage
from langchain_nvidia_ai_endpoints import ChatNVIDIA

from packages.config import get_settings

Profile = Literal["fast", "reason"]
_T = TypeVar("_T")

# Toggle de raciocínio do Nemotron: controlado por system message dedicado,
# não por parâmetro do cliente. Nano roda sempre OFF; Super liga conforme a tarefa.
_THINKING_ON = "detailed thinking on"
_THINKING_OFF = "detailed thinking off"

# Defaults de amostragem por perfil (recomendação NVIDIA p/ Nemotron):
# reasoning ON → temperature 0.6 / top_p 0.95; roteamento/normalização → greedy.
_SAMPLING: dict[Profile, dict[str, float]] = {
    "fast": {"temperature": 0.0, "top_p": 1.0},
    "reason": {"temperature": 0.6, "top_p": 0.95},
}

# Teto de saída por perfil. O default da lib (ChatNVIDIA) é **1024**, que estoura no `reason`:
# o Super com reasoning ON gasta o orçamento na cadeia de raciocínio e é **truncado antes de
# emitir o JSON** → o parser do nó devolve None e o run degrada sem diagnóstico. Por isso o
# `reason` precisa de folga p/ a CoT + o JSON final; o `fast` (Nano, greedy) tem saídas curtas.
_MAX_TOKENS: dict[Profile, int] = {
    "fast": 2048,
    "reason": 8192,
}


def reasoning_system_message(enabled: bool = True) -> SystemMessage:
    """System message que liga/desliga o reasoning do Nemotron-Super.

    Os nós (F2) prefixam isto no prompt versionado (F0.12): `reason`/Super liga
    conforme a tarefa (classifier/recommender/briefing); `fast`/Nano não usa.
    """
    return SystemMessage(content=_THINKING_ON if enabled else _THINKING_OFF)


@lru_cache
def get_chat(
    profile: Profile = "fast",
    *,
    self_hosted: bool = False,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> ChatNVIDIA:
    """Cliente Nemotron por perfil (F0.7), cacheado por combinação de argumentos.

    - `fast`   → Nano (`NEMOTRON_MODEL_FAST`).
    - `reason` → Super (`NEMOTRON_MODEL_REASON`); ligue o reasoning com
      `reasoning_system_message`.

    `self_hosted=True` aponta para o NIM local (GPU, `NIM_BASE_URL`); caso contrário
    usa o catálogo build.nvidia.com com `NVIDIA_API_KEY`. `temperature` sobrepõe o
    default do perfil.
    """
    s = get_settings()
    model = s.nemotron_model_fast if profile == "fast" else s.nemotron_model_reason
    sampling = _SAMPLING[profile]

    kwargs: dict = {
        "model": model,
        "temperature": sampling["temperature"] if temperature is None else temperature,
        "top_p": sampling["top_p"],
        # Sobrepõe o default 1024 da lib (insuficiente p/ o reasoning do Super, ver _MAX_TOKENS).
        "max_tokens": _MAX_TOKENS[profile] if max_tokens is None else max_tokens,
    }
    if self_hosted:
        kwargs["base_url"] = s.nim_base_url
    elif s.nvidia_api_key:
        kwargs["api_key"] = s.nvidia_api_key

    chat = ChatNVIDIA(**kwargs)
    _stretch_read_timeout(chat)
    return chat


def _stretch_read_timeout(chat: ChatNVIDIA) -> None:
    """Estica o read timeout do cliente HTTP do SDK NVIDIA (default **60s**) p/ caber sob o guard
    de parede (F7.6). O Super com reasoning ON + payload de extração às vezes passa de 60s e o SDK
    levantava `requests.ReadTimeout` (diag rivio.ai: `read timeout=60`) antes do guard de 120s,
    derrubando a extração. Alinha um pouco ABAIXO do guard p/ o read timeout (`integrate.api...`)
    — que agora é **retryável** (`cache._invoke_chat`) — disparar limpo antes do thread-join. Best-
    effort: mexe num atributo do cliente do SDK (`_client.timeout`), que pode mudar entre versões.
    """
    guard = request_timeout_seconds()
    target = guard - 5.0 if guard > 5.0 else 115.0  # guard 0 (desligado) → valor generoso fixo
    try:
        chat._client.timeout = target  # noqa: SLF001 — campo do cliente do SDK, sem setter público
    except Exception:  # noqa: BLE001 — atributo privado pode sumir entre versões → mantém o default
        pass


# ----------------------------------------------------------------- timeout (F7.6)


class LLMTimeout(TimeoutError):
    """Uma chamada de LLM excedeu o teto de tempo de parede (F7.6).

    Tratada como qualquer falha de LLM: os nós (F2.5/F2.6/F4.2/F4.4) já caem no caminho
    determinista a qualquer exceção, então o run segue offline, sem alucinar, e carimba a
    nota rastreável. Subclasse de `TimeoutError` (logo `Exception`) p/ casar nesses `except`.
    """

    def __init__(self, seconds: float) -> None:
        super().__init__(f"chamada de LLM excedeu {seconds:g}s (F7.6)")
        self.seconds = seconds


def request_timeout_seconds() -> float:
    """Teto de tempo (s) por chamada de LLM, do settings (F7.6); 0 = sem teto."""
    return max(0.0, float(get_settings().llm_request_timeout_seconds))


def run_with_timeout(call: Callable[[], _T], *, seconds: float | None = None) -> _T:
    """Executa `call` com teto de tempo de PAREDE (F7.6); levanta `LLMTimeout` no estouro.

    Por quê uma thread: o `timeout` da lib (langchain-nvidia-ai-endpoints) só cobre o poll
    após um 202 — o socket de `session.post` não tem teto, então uma conexão pendurada travaria
    o run. Aqui a chamada roda numa thread daemon e a espera é limitada a `seconds`; estourou →
    `LLMTimeout` (o caller LLM degrada p/ o determinista). A thread órfã é daemon: **não** trava
    a saída do processo e seu resultado tardio é descartado.

    Propaga o **contexto** (`contextvars.copy_context()`) p/ a thread: a captura de uso/orçamento
    (F2.9/F2.11) vive em `ContextVar` e NÃO atravessaria uma thread nova sozinha — sem isso o
    `UsageRecorder`/`BudgetGuard` parariam de medir/limitar. Como o escopo guarda o uso numa
    lista (o `copy_context` compartilha a referência), o que o callback registra na worker é
    visível ao rollup do run. `seconds=None` lê o settings; `0` = sem teto (roda inline).
    """
    secs = request_timeout_seconds() if seconds is None else max(0.0, float(seconds))
    if not secs:
        return call()
    ctx = contextvars.copy_context()
    box: dict[str, object] = {}

    def _worker() -> None:
        try:
            box["value"] = ctx.run(call)
        except BaseException as exc:  # noqa: BLE001 - repassa a falha real à thread principal
            box["error"] = exc

    thread = threading.Thread(target=_worker, name="tapi-llm-timeout", daemon=True)
    thread.start()
    thread.join(secs)
    if thread.is_alive():
        raise LLMTimeout(secs)
    if "error" in box:
        raise box["error"]  # type: ignore[misc]
    return box["value"]  # type: ignore[return-value]


def smoke(profile: Profile = "fast") -> str:
    """Smoke test (F0.7): chamada real mínima ao Nemotron; retorna o texto.

    Requer `NVIDIA_API_KEY`. Usado pelo `__main__` e pelo teste de integração (pulado
    sem chave). Com o Langfuse ligado (F0.8), a chamada vai com o callback de tracing
    e aparece como trace — critério de DoD da F0.8. A chamada passa pelo teto de tempo (F7.6).
    """
    from langchain_core.messages import HumanMessage

    from packages.observability import flush_tracing, traced_config

    messages: list = []
    if profile == "reason":
        messages.append(reasoning_system_message(True))
    messages.append(HumanMessage(content="Responda apenas com a palavra: OK"))
    config = traced_config(node=f"smoke:{profile}")
    out = run_with_timeout(lambda: get_chat(profile).invoke(messages, config=config)).content
    flush_tracing()
    return out


if __name__ == "__main__":  # pragma: no cover
    import sys

    if not get_settings().nvidia_api_key:
        sys.exit("NVIDIA_API_KEY ausente — configure o .env antes do smoke test (F0.7).")
    for _profile in ("fast", "reason"):
        print(f"[{_profile}] ->", smoke(_profile).strip()[:200])
