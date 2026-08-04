"""Progresso ao vivo do run — eventos por nó + canal Redis pub/sub (F2.10).

O worker (`apps/worker`, F2.10) roda o grafo num job assíncrono e **publica** o
progresso num canal **Redis pub/sub por `run_id`**; o endpoint SSE da API (F5.2/F5.3)
**assina** o canal e repassa ao front. Este módulo é a fronteira entre os dois:

- `ProgressEvent` — contrato mínimo do evento (`{run_id, node, status, pct, ts}` + `extra`).
- `stream_pipeline` — roda o grafo com `.stream()` e dispara um `ProgressEvent` por nó
  num hook injetável `on_event` (o publisher). Espelha o `run_pipeline` (F2.1): mesmo
  `traced_config`/`capture_usage` (F2.9), mas emite progresso enquanto anda.
- `progress_channel` / `RedisProgressPublisher` / `subscribe_progress` — o transporte: o
  publisher serializa o evento e dá `PUBLISH` no canal; o subscriber é o **consumidor**
  que a F5.3 embrulha em SSE. O cliente Redis é **injetado** (testável sem broker).

**Offline é o default (igual F2.3–F2.9):** sem `on_event` o stream só roda o grafo (que
já é offline/reproduzível, M2/DoD); o Redis só entra quando um cliente é passado. Publicar
é **best-effort** — uma falha de broker (`RedisError`) não derruba o run; o progresso é
telemetria, não o resultado.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol

from pydantic import BaseModel, ConfigDict, Field
from redis.exceptions import RedisError

from packages.schemas import ExecutionMode, GraphState, HITLMode, RunStatus

from .graph import PIPELINE, RUN_NAME, compile_graph, stamp_usage

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.graph.state import CompiledStateGraph
    from redis import Redis

    from packages.observability import LLMBudget, TokenUsage

#: Nó sentinela do **evento terminal** (run encerrou/pausou). O consumidor SSE (F5.3) o
#: lê para fechar o stream; `status` carrega o desfecho real (completed/awaiting_review/…).
END_NODE = "__end__"

#: Prefixo do canal pub/sub; um canal por `run_id` (isola os assinantes de cada run).
CHANNEL_PREFIX = "tapi:progress:"


def progress_channel(run_id: str) -> str:
    """Nome do canal Redis pub/sub do run (publisher e subscriber concordam aqui)."""
    return f"{CHANNEL_PREFIX}{run_id}"


def _now() -> datetime:
    return datetime.now(UTC)


class ProgressEvent(BaseModel):
    """Evento de progresso de um run (contrato worker → SSE, F2.10).

    `node` é o nó que acabou de rodar (ou `END_NODE` no evento terminal); `status` é o
    estado do run no momento (`RunStatus`); `pct` é a posição na espinha (0–100). `extra`
    leva payload opcional sem quebrar o contrato mínimo.
    """

    model_config = ConfigDict(extra="forbid")

    run_id: str
    node: str
    status: str = Field(description="Estado do run no evento (valor de RunStatus).")
    pct: int | None = Field(default=None, ge=0, le=100)
    ts: datetime = Field(default_factory=_now)
    extra: dict = Field(default_factory=dict)


class ProgressPublisher(Protocol):
    """Sink de progresso: recebe cada `ProgressEvent`. O `on_event` do `stream_pipeline`."""

    def __call__(self, event: ProgressEvent) -> None: ...


def _pct(node: str) -> int | None:
    """Progresso (0–100) pela posição do nó na espinha (F2.1). Sentinelas → None."""
    if node not in PIPELINE:
        return None
    return round((PIPELINE.index(node) + 1) / len(PIPELINE) * 100)


def _publish(
    on_event: Callable[[ProgressEvent], None] | None,
    run_id: str,
    node: str,
    status: str,
    pct: int | None,
) -> None:
    """Emite um `ProgressEvent` no sink, se houver (no-op offline, sem `on_event`)."""
    if on_event is not None:
        on_event(ProgressEvent(run_id=run_id, node=node, status=status, pct=pct))


def _drive(
    compiled: CompiledStateGraph,
    inp: Any,
    config: dict,
    *,
    run_id: str,
    fallback: GraphState,
    budget: LLMBudget | None,
    on_event: Callable[[ProgressEvent], None] | None,
) -> tuple[GraphState, TokenUsage]:
    """Núcleo de streaming: roda o grafo, emite um evento por nó e devolve (estado, uso).

    Compartilhado por `stream_pipeline` (run novo, `inp=GraphState`) e `resume_pipeline`
    (retomada, `inp=Command(resume=...)`). `stream_mode=["updates","values"]`: **updates** dá o
    nó que acabou (→ evento `running`), **values** acumula o estado cheio. Sentinelas do
    LangGraph (`__interrupt__`, …) são puladas. Sem `values` acumulado devolve o `fallback`. O
    `capture_usage` (F2.9) soma tokens/custo no escopo, com a guarda de orçamento (F2.11).
    """
    from packages.observability import capture_usage

    latest: dict[str, Any] | None = None
    with capture_usage(budget=budget) as usage:
        for stream_mode, chunk in compiled.stream(inp, config, stream_mode=["updates", "values"]):
            if stream_mode == "values":
                # No interrupt (F2.8) o chunk de values carrega um `__interrupt__` extra; o
                # estado é `extra="forbid"`, então fica só com os campos próprios do estado.
                latest = {k: v for k, v in chunk.items() if not k.startswith("__")}
                continue
            for node in chunk:  # updates: {node: update} — espinha linear (1 chave)
                if node.startswith("__"):  # __interrupt__ etc. não é nó da espinha
                    continue
                _publish(on_event, run_id, node, RunStatus.RUNNING.value, _pct(node))
        total = usage.total()

    state = GraphState.model_validate(latest) if latest is not None else fallback
    return state, total


def stream_pipeline(
    query: str,
    *,
    run_id: str | None = None,
    mode: ExecutionMode = ExecutionMode.SINGLE_COMPANY,
    hitl: HITLMode = HITLMode.SYNC,
    checkpointer: BaseCheckpointSaver | None = None,
    on_event: Callable[[ProgressEvent], None] | None = None,
    budget: LLMBudget | None = None,
) -> GraphState:
    """Roda o grafo com `.stream()`, emitindo um `ProgressEvent` por nó, e devolve o estado.

    Variante streaming do `run_pipeline` (F2.1) para o worker (F2.10): reusa o mesmo
    `traced_config` (span por nó, F2.9), o `capture_usage` (rollup de tokens em
    `trace["usage"]`) e a guarda de orçamento (F2.11 — `budget`/`budget_from_settings`,
    estampada por `stamp_usage`). O streaming por nó roda no núcleo `_drive`.

    Ao fim, emite **um evento terminal** (`node=END_NODE`, `pct=100`) com o desfecho real:
    se o grafo pausou para HITL sync (F2.8 — `checkpointer` presente e há nó pendente),
    o status é `awaiting_review`; senão, o `status` do estado final
    (`completed`/`insufficient_data`/`out_of_scope`, F2.12/F2.13). Sem `on_event` nada é
    publicado (offline default); o grafo roda igual ao `run_pipeline`.
    """
    from packages.observability import budget_from_settings, traced_config

    run_id = run_id or uuid.uuid4().hex
    init = GraphState(run_id=run_id, query=query, mode=mode, hitl=hitl)
    budget = budget if budget is not None else budget_from_settings()

    config = traced_config(node=RUN_NAME, run_id=run_id)
    if checkpointer is not None:
        config["configurable"] = {"thread_id": run_id}

    compiled = compile_graph(checkpointer=checkpointer)
    state, total = _drive(
        compiled, init, config, run_id=run_id, fallback=init, budget=budget, on_event=on_event
    )

    # Pausa HITL sync (F2.8) só existe com checkpointer; nó pendente ⇒ awaiting_review.
    interrupted = checkpointer is not None and bool(compiled.get_state(config).next)

    state = stamp_usage(state, total, budget)
    final_status = RunStatus.AWAITING_REVIEW.value if interrupted else state.status.value
    _publish(on_event, run_id, END_NODE, final_status, 100)
    return state


def resume_pipeline(
    run_id: str,
    decision: Any,
    *,
    checkpointer: BaseCheckpointSaver,
    on_event: Callable[[ProgressEvent], None] | None = None,
    budget: LLMBudget | None = None,
) -> GraphState:
    """Retoma um run pausado no HITL sync (F2.8) com a decisão humana e segue até o fim.

    Contraparte do `stream_pipeline` para o `POST /runs/{id}/resume` (F5.2): o run já correu
    até o interrupt do `human_review` e ficou **persistido** na thread `run_id` (checkpointer
    F2.2). A execução retoma com `Command(resume=decision)` — o valor vira o retorno do
    `interrupt()`, registrado em `trace["human_review"]` (auditável) — emitindo progresso só
    dos nós restantes (`human_review` → `briefing`) + o **terminal** (`completed`, ou de novo
    `awaiting_review` se o run tornar a pausar). Requer o `checkpointer` com a thread pausada
    (a API abre o Postgres/F2.2; testes injetam um `InMemorySaver` já interrompido).
    """
    from langgraph.types import Command

    from packages.observability import budget_from_settings, traced_config

    budget = budget if budget is not None else budget_from_settings()
    config = traced_config(node=RUN_NAME, run_id=run_id)
    config["configurable"] = {"thread_id": run_id}

    compiled = compile_graph(checkpointer=checkpointer)
    fallback = GraphState.model_validate(compiled.get_state(config).values)
    state, total = _drive(
        compiled,
        Command(resume=decision),
        config,
        run_id=run_id,
        fallback=fallback,
        budget=budget,
        on_event=on_event,
    )

    interrupted = bool(compiled.get_state(config).next)
    state = stamp_usage(state, total, budget)
    final_status = RunStatus.AWAITING_REVIEW.value if interrupted else state.status.value
    _publish(on_event, run_id, END_NODE, final_status, 100)
    return state


class RedisProgressPublisher:
    """`ProgressPublisher` que dá `PUBLISH` do evento (JSON) no canal pub/sub do run.

    O cliente Redis é **injetado** (produção: `redis.Redis.from_url(settings.redis_url)`;
    teste: um stub que registra os `publish`). Publicar é **best-effort**: uma falha de
    broker (`RedisError`) é engolida — o progresso é telemetria e não pode derrubar o run.
    """

    def __init__(self, client: Redis) -> None:
        self._client = client

    def __call__(self, event: ProgressEvent) -> None:
        try:
            self._client.publish(progress_channel(event.run_id), event.model_dump_json())
        except RedisError:
            pass  # broker indisponível não derruba o run (progresso é best-effort)


def subscribe_progress(
    client: Redis, run_id: str, *, timeout: float | None = None
) -> Iterator[ProgressEvent]:
    """Assina o canal do run e itera os `ProgressEvent` até o terminal (`END_NODE`).

    **Consumidor** do canal — a F5.3 embrulha isto num endpoint SSE (`GET /runs/{id}`).
    O cliente Redis é injetado; `timeout` (s) limita a espera por mensagem (None = bloqueia
    até a próxima). Mensagens não-`message` (confirmação de subscribe) são ignoradas.
    """
    pubsub = client.pubsub()
    pubsub.subscribe(progress_channel(run_id))
    try:
        while True:
            msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=timeout)
            if msg is None:
                if timeout is not None:
                    break  # estourou a espera sem evento — devolve o controle ao chamador
                continue
            event = ProgressEvent.model_validate_json(msg["data"])
            yield event
            if event.node == END_NODE:
                break
    finally:
        pubsub.close()
