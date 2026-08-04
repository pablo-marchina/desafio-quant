"""Bootstrap do Langfuse e wrapper de callback p/ os LLMs (F0.8).

Langfuse **v3** (SDK 4.x, baseado em OpenTelemetry) — casa com o servidor
`langfuse/langfuse:3` do compose. O cliente é um singleton global: basta construí-lo
uma vez (aqui) e os `CallbackHandler` herdam essa config. Tudo é **no-op** sem as duas
chaves (`langfuse_enabled`, F0.3), então roda em CI/local sem Langfuse no ar.

Os nós (F2) passam `traced_config(node=..., prompt_version=...)` no `.invoke(config=...)`;
o `prompt_version` (F0.12) entra no metadata do trace e o `run_id` correlaciona
trace ↔ tabela `run` (F0.6).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

from packages.config import get_settings

from .cost import BUDGET_GUARD, USAGE_RECORDER


@lru_cache
def get_langfuse() -> Langfuse | None:
    """Cliente Langfuse (singleton, cacheado). None quando as chaves não estão setadas.

    Construir o cliente registra o singleton global do SDK; os `CallbackHandler`
    criados depois herdam host/chaves dele.
    """
    s = get_settings()
    if not s.langfuse_enabled:
        return None
    return Langfuse(
        public_key=s.langfuse_public_key,
        secret_key=s.langfuse_secret_key,
        host=s.langfuse_host,
    )


def get_callback_handler() -> CallbackHandler | None:
    """Handler LangChain/LangGraph p/ `.invoke(config={'callbacks': [...]})`.

    None quando o tracing está desligado. Garante o cliente construído antes (senão o
    handler nasceria sem config e emitiria aviso de autenticação).
    """
    if get_langfuse() is None:
        return None
    return CallbackHandler()


def langfuse_callbacks() -> list[Any]:
    """Callbacks p/ o RunnableConfig — lista vazia quando o tracing está off."""
    handler = get_callback_handler()
    return [handler] if handler is not None else []


def traced_config(
    *,
    node: str | None = None,
    prompt_version: str | None = None,
    run_id: str | None = None,
    **metadata: Any,
) -> dict[str, Any]:
    """RunnableConfig com callback Langfuse + metadata carimbado no trace.

    `node` vira o nome do span/run e uma tag; `prompt_version` (F0.12) e `run_id`
    entram no metadata p/ correlacionar trace ↔ `run`. Sem Langfuse, os callbacks ficam
    só com o `USAGE_RECORDER` (medição de tokens/custo local, F2.9) — inócuo offline,
    então os nós chamam isto incondicionalmente. O recorder é singleton: aparecendo nos
    níveis aninhados do grafo, o LangChain o deduplica por identidade (sem dupla contagem).
    """
    meta: dict[str, Any] = dict(metadata)
    if prompt_version is not None:
        meta["prompt_version"] = prompt_version
    if run_id is not None:
        meta["run_id"] = run_id

    # USAGE_RECORDER (F2.9) + BUDGET_GUARD (F2.11) sempre presentes — medem/limitam tokens
    # mesmo sem Langfuse no ar (inócuos offline: sem LLM nada dispara, sem budget nada barra);
    # os handlers do Langfuse só entram quando o tracing está ligado (duas chaves, F0.3).
    callbacks: list[Any] = [USAGE_RECORDER, BUDGET_GUARD, *langfuse_callbacks()]
    config: dict[str, Any] = {"callbacks": callbacks, "metadata": meta}
    if node is not None:
        config["run_name"] = node
        meta.setdefault("langfuse_tags", []).append(node)
    return config


def flush_tracing() -> None:
    """Força o envio dos traces pendentes (scripts curtos/smoke). No-op sem cliente."""
    client = get_langfuse()
    if client is not None:
        client.flush()
