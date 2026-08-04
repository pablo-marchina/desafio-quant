"""Job RQ que roda um run do grafo de forma assíncrona (F2.10).

Runs longos (coleta + 3 chamadas LLM) não cabem no request HTTP — a API (F5.2) só
**enfileira** (`enqueue_run`) e responde o `run_id`; um worker RQ (`rq worker tapi`)
puxa o job e roda o grafo **persistido** (checkpointer Postgres, F2.2), publicando o
progresso no canal Redis pub/sub do run (F2.10/`packages.agents.progress`) que o SSE
da F5.3 assina.

**Conexões nascem dentro do job, não viajam na fila:** o RQ serializa os argumentos
(pickle), então não dá para passar Redis/Postgres vivos pelo enqueue — o job abre o
checkpointer e o cliente Redis a partir do `settings` (F0.3) quando o worker o executa.
Para teste offline, o núcleo (`run_graph_job`) recebe esses recursos **injetados**
(`redis_client`, `open_checkpointer`, `runner`), rodando sem broker nem banco.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from packages.agents.checkpoint import postgres_checkpointer
from packages.agents.progress import RedisProgressPublisher, resume_pipeline, stream_pipeline
from packages.config import get_settings
from packages.schemas import ExecutionMode, HITLMode

from .persistence import persist_run_state

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractContextManager

    from langgraph.checkpoint.base import BaseCheckpointSaver
    from redis import Redis
    from rq import Queue
    from sqlmodel import Session

    from packages.agents.progress import ProgressEvent
    from packages.schemas import GraphState

    #: Fábrica de checkpointer: abre um context manager que entrega o saver (ou None offline).
    _OpenCheckpointer = Callable[[], AbstractContextManager[BaseCheckpointSaver | None]]
    #: Fábrica de sessão SQL: abre um context manager que entrega a Session (ou None offline).
    _OpenSession = Callable[[], AbstractContextManager[Session | None]]


def _redis_from_settings() -> Redis:
    """Cliente Redis a partir da config (F0.3). Conecta lazy — não toca o broker aqui."""
    from redis import Redis

    return Redis.from_url(get_settings().redis_url)


def _default_checkpointer() -> AbstractContextManager[BaseCheckpointSaver]:
    """Abre o checkpointer Postgres de produção (resume/retry, F2.2)."""
    return postgres_checkpointer()


def _default_session() -> AbstractContextManager[Session]:
    """Abre a sessão SQL de produção (F0.6) — onde as saídas do run são gravadas (F2.10)."""
    from sqlmodel import Session

    from packages.db import get_engine

    return Session(get_engine())


def _persist_run(state: GraphState, open_session: _OpenSession | None) -> None:
    """Grava as saídas do run nas tabelas relacionais (F0.6) e **commita** — fecha o run e2e.

    Pós-run (estado final → `run`/`company`/`score`/`recommendation`, `packages.agents` +
    `apps.worker.persistence`) numa transação própria, separada do checkpointer (F2.2). A
    sessão é **injetável** (`open_session`) e, quando o factory entrega `None` (offline/sem
    banco), é um no-op limpo — o grafo roda igual sem tocar o Postgres (M2/DoD).
    """
    open_db = open_session or _default_session
    with open_db() as session:
        if session is None:
            return  # offline (sem banco) → só roda o grafo, não persiste
        persist_run_state(session, state)
        session.commit()


def run_graph_job(
    query: str,
    *,
    run_id: str | None = None,
    mode: ExecutionMode | str = ExecutionMode.SINGLE_COMPANY,
    hitl: HITLMode | str = HITLMode.SYNC,
    redis_client: Redis | None = None,
    open_checkpointer: _OpenCheckpointer | None = None,
    open_session: _OpenSession | None = None,
    runner: Callable[..., GraphState] = stream_pipeline,
) -> dict[str, Any]:
    """Roda um run do grafo (persistido), publica o progresso e **grava as saídas**; resumo.

    É a função que o worker RQ executa. Coage `mode`/`hitl` de string (sobrevivem ao
    pickle da fila como enum, mas a API/CLI podem mandar texto). Abre o checkpointer
    Postgres, o publisher Redis e a sessão SQL de produção por default; os três são
    **injetáveis** para teste offline. Ao fim, persiste o run inteiro (run/company/score/
    recs, F0.6) a partir do estado final (`_persist_run`) — é o que alimenta `GET /companies`
    (F5.4). O resumo (`{run_id, status, query, needs_review}`) é o retorno do job que a API lê.
    """
    run_id = run_id or uuid.uuid4().hex
    mode = ExecutionMode(mode)
    hitl = HITLMode(hitl)

    client = redis_client if redis_client is not None else _redis_from_settings()
    publisher: Callable[[ProgressEvent], None] | None = (
        RedisProgressPublisher(client) if client is not None else None
    )
    open_cp = open_checkpointer or _default_checkpointer

    with open_cp() as checkpointer:
        state = runner(
            query,
            run_id=run_id,
            mode=mode,
            hitl=hitl,
            checkpointer=checkpointer,
            on_event=publisher,
        )

    _persist_run(state, open_session)

    return {
        "run_id": run_id,
        "status": state.status.value,
        "query": query,
        "needs_review": state.needs_review,
    }


def resume_graph_job(
    run_id: str,
    decision: Any,
    *,
    redis_client: Redis | None = None,
    open_checkpointer: _OpenCheckpointer | None = None,
    open_session: _OpenSession | None = None,
    runner: Callable[..., GraphState] = resume_pipeline,
) -> dict[str, Any]:
    """Retoma um run pausado no HITL (F2.8) com a decisão humana; devolve um resumo (F5.2).

    Job RQ irmão do `run_graph_job`: o `POST /runs/{id}/resume` (F5.2) o enfileira quando o
    gerente aprova/edita/rejeita na tela de revisão (F5.10). Abre o **mesmo** checkpointer
    Postgres (F2.2) — a thread `run_id` está pausada lá — o publisher Redis e a sessão SQL de
    produção por default; os três **injetáveis** para teste offline. Publica o progresso dos
    nós restantes e **re-persiste** o run (idempotente): a linha `run` sai de `awaiting_review`
    para o desfecho final (`completed`/terminal) e o briefing/score/recs ficam gravados. Devolve
    `{run_id, status, needs_review}`.
    """
    client = redis_client if redis_client is not None else _redis_from_settings()
    publisher: Callable[[ProgressEvent], None] | None = (
        RedisProgressPublisher(client) if client is not None else None
    )
    open_cp = open_checkpointer or _default_checkpointer

    with open_cp() as checkpointer:
        state = runner(run_id, decision, checkpointer=checkpointer, on_event=publisher)

    _persist_run(state, open_session)

    return {
        "run_id": run_id,
        "status": state.status.value,
        "needs_review": state.needs_review,
    }


def default_queue(*, connection: Redis | None = None) -> Queue:
    """Fila RQ `tapi` ligada ao Redis da config (F0.3). Onde a API enfileira e o worker puxa."""
    from rq import Queue

    return Queue("tapi", connection=connection or _redis_from_settings())


def _job_timeout() -> int:
    """Teto do job RQ por run (F2.10), do settings; `-1` = sem teto (convenção do RQ).

    O default do RQ (180s) mata um run real no meio (coleta + LLM com reasoning + retries F7.6):
    foi o `JobTimeoutException` que degradou a extração da rivio.ai mesmo com o read timeout já
    esticado. `worker_job_timeout_seconds=0` vira `-1` (sem teto).
    """
    secs = get_settings().worker_job_timeout_seconds
    return secs if secs > 0 else -1


def enqueue_run(
    query: str,
    *,
    queue: Queue,
    run_id: str | None = None,
    mode: ExecutionMode | str = ExecutionMode.SINGLE_COMPANY,
    hitl: HITLMode | str = HITLMode.SYNC,
) -> str:
    """Enfileira um run e devolve o `run_id` (a API responde isso; o SSE acompanha o canal).

    `job_id=run_id` casa o job RQ com o `run_id` (= thread do checkpointer e canal de
    progresso), então o mesmo identificador rastreia o run de ponta a ponta. Só os
    argumentos planos viajam na fila; o job abre Redis/Postgres ao rodar.
    """
    run_id = run_id or uuid.uuid4().hex
    mode = ExecutionMode(mode)
    hitl = HITLMode(hitl)
    queue.enqueue(
        run_graph_job,
        query,
        run_id=run_id,
        mode=mode.value,
        hitl=hitl.value,
        job_id=run_id,
        job_timeout=_job_timeout(),
    )
    return run_id


def resume_job_id(run_id: str) -> str:
    """ID do job RQ de resume (F2.8) — fonte única do formato (usado no enqueue e no `/status`).

    Sufixo com **dash**, não `:`: o RQ valida o `job_id` (`validate_job_id`) e **rejeita** dois-
    pontos — só aceita letras/números/`_`/`-`. Um `f"{run_id}:resume"` estourava `ValueError`
    no primeiro resume ao vivo (os testes usam fila fake que não valida). O `run_id` é um uuid4
    hex (sem dash), então `{run_id}-resume` é inequívoco e distingue do original (`job_id=run_id`).
    """
    return f"{run_id}-resume"


def enqueue_resume(run_id: str, decision: Any, *, queue: Queue) -> str:
    """Enfileira a retomada de um run pausado no HITL (F2.8) e devolve o `run_id` (F5.2).

    `job_id=resume_job_id(run_id)` distingue o job de resume do job original (`job_id=run_id`),
    que pode seguir no registro do RQ — mesmo `run_id` (= thread/canal de progresso), job RQ
    distinto. Só argumentos planos viajam na fila; o job abre Redis/Postgres ao rodar.
    """
    queue.enqueue(
        resume_graph_job, run_id, decision, job_id=resume_job_id(run_id), job_timeout=_job_timeout()
    )
    return run_id
