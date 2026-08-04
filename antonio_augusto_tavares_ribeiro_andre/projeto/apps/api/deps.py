"""Dependências (DI) da API TAPI (F5.2) — recursos de produção, sobrescrevíveis em teste.

Cada provider entrega um recurso vivo por padrão (fila RQ, canal de progresso Redis, sessão
SQL, leitor de briefing) montado a partir da config (F0.3). Os endpoints os recebem via
`Depends`, e os testes trocam por stubs offline com `app.dependency_overrides` — mesmo ethos
de "injetável p/ teste offline" do worker (F2.10) e da persistência (F4.7), sem broker/banco.

A **autenticação** (gate interno por API key/bearer) é a F5.9: entra aqui como uma dependência
aplicada aos endpoints; a F5.2 só monta as rotas e deixa o gancho documentado.
"""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Header, HTTPException, Query

from packages.db.engine import get_session

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from rq import Queue

    from packages.agents.progress import ProgressEvent
    from packages.schemas import Briefing, GraphState

# Sessão SQL por requisição: reusa a dependência do engine (F0.6) — fecha ao fim do escopo.
db_session = get_session


def get_queue() -> Queue:
    """Fila RQ `tapi` ligada ao Redis da config (F0.3) — onde `POST /runs`/`/resume` enfileiram."""
    from apps.worker import default_queue

    return default_queue()


def get_progress_source() -> Callable[[str], Iterable[ProgressEvent]]:
    """Fonte de progresso de um run: assina o canal Redis pub/sub (F2.10) e itera os eventos.

    O `GET /runs/{id}` (SSE, F5.3) embrulha cada `ProgressEvent` em `text/event-stream`. Em
    teste, sobrescreve-se por um gerador de eventos canônicos (sem broker).
    """
    from packages.agents.progress import subscribe_progress
    from packages.config import get_settings

    def _source(run_id: str) -> Iterable[ProgressEvent]:
        from redis import Redis

        client = Redis.from_url(get_settings().redis_url)
        return subscribe_progress(client, run_id)

    return _source


def get_job_phase() -> Callable[[str], str]:
    """Fase do job RQ de um run (F2.10): `running` | `failed` | `finished` | `absent`.

    Sinal **autoritativo** de "ainda rodando" que o checkpoint sozinho não dá — pausado no HITL
    (F2.8) e mid-flight têm ambos `next` não-vazio no snapshot. `job_id=run_id` (e `resume_job_id`
    no resume) casa o job RQ com o run (`apps/worker/jobs.py`), então olhar os dois cobre o ciclo:
    qualquer um na fila/executando ⇒ `running`; algum falhou ⇒ `failed`; concluídos ⇒ `finished`;
    nenhum encontrado (job expirou do RQ ou run inexistente) ⇒ `absent`. Em teste, sobrescreve-se.
    """
    from packages.config import get_settings

    def _phase(run_id: str) -> str:
        from redis import Redis
        from rq.exceptions import NoSuchJobError
        from rq.job import Job

        from apps.worker import resume_job_id

        conn = Redis.from_url(get_settings().redis_url)
        statuses: list[str] = []
        for jid in (run_id, resume_job_id(run_id)):
            try:
                statuses.append(str(Job.fetch(jid, connection=conn).get_status(refresh=True)))
            except NoSuchJobError:
                continue
        if not statuses:
            return "absent"
        if any(s in {"queued", "started", "deferred", "scheduled"} for s in statuses):
            return "running"
        if any(s == "failed" for s in statuses):
            return "failed"
        return "finished"

    return _phase


def get_briefing_loader() -> Callable[[str], Briefing | None]:
    """Leitor do briefing de um run (`GET /briefings/{id}`, F5.2): lê do checkpoint (F2.2).

    O briefing final (F4.4) vive no estado persistido da thread `run_id` (não há tabela
    própria); abre o checkpointer Postgres e devolve o `Briefing` do snapshot, ou `None` se o
    run não chegou ao briefing. Em teste, sobrescreve-se por um loader que devolve um `Briefing`.
    """
    from packages.agents.checkpoint import postgres_checkpointer
    from packages.agents.graph import compile_graph
    from packages.schemas import Briefing

    def _load(run_id: str) -> Briefing | None:
        with postgres_checkpointer(setup=False) as cp:
            snapshot = compile_graph(checkpointer=cp).get_state(
                {"configurable": {"thread_id": run_id}}
            )
        data = snapshot.values.get("briefing") if snapshot.values else None
        return Briefing.model_validate(data) if data else None

    return _load


def get_trace_loader() -> Callable[[str], GraphState | None]:
    """Leitor do estado persistido de um run (F5.7) — lê do checkpoint (F2.2) p/ o trace viewer.

    Espelha o `get_briefing_loader`, mas devolve o **estado inteiro** (`GraphState`) para a
    projeção do trace (passos dos agentes + custo, ver `apps/api/trace.py`); `None` se o run não
    tem checkpoint (run inexistente). Em teste, sobrescreve-se por um loader que devolve um
    `GraphState` montado à mão.
    """
    from packages.agents.checkpoint import postgres_checkpointer
    from packages.agents.graph import compile_graph
    from packages.schemas import GraphState

    def _load(run_id: str) -> GraphState | None:
        with postgres_checkpointer(setup=False) as cp:
            snapshot = compile_graph(checkpointer=cp).get_state(
                {"configurable": {"thread_id": run_id}}
            )
        return GraphState.model_validate(snapshot.values) if snapshot.values else None

    return _load


def get_review_loader() -> Callable[[str], tuple[GraphState, bool] | None]:
    """Leitor do estado + flag de pausa de um run (F5.10) — para a tela de revisão HITL.

    Espelha o `get_trace_loader`, mas além do `GraphState` reporta se o run está **pausado no
    interrupt** sync (F2.8): `snapshot.next` não-vazio = o `human_review` está aguardando a
    decisão humana. Devolve `(GraphState, awaiting)`, ou `None` se o run não tem checkpoint (run
    inexistente → 404). Em teste, sobrescreve-se por um loader que devolve um `GraphState` montado
    à mão + a flag.
    """
    from packages.agents.checkpoint import postgres_checkpointer
    from packages.agents.graph import compile_graph
    from packages.schemas import GraphState

    def _load(run_id: str) -> tuple[GraphState, bool] | None:
        with postgres_checkpointer(setup=False) as cp:
            snapshot = compile_graph(checkpointer=cp).get_state(
                {"configurable": {"thread_id": run_id}}
            )
        if not snapshot.values:
            return None
        return GraphState.model_validate(snapshot.values), bool(snapshot.next)

    return _load


def get_langfuse_url() -> str | None:
    """Host do Langfuse (deep-trace, F0.8) p/ o trace viewer (F5.7) — `None` com o tracing off.

    Sem um `trace_id` persistido não há deep-link por run; expomos o host (quando as duas chaves
    estão setadas, F0.3) como ponto de entrada e mantemos o passo-a-passo do viewer no estado do
    grafo (offline-reproduzível).
    """
    from packages.config import get_settings

    s = get_settings()
    return s.langfuse_host if s.langfuse_enabled else None


# --- Auth (gate interno — F5.9) ----------------------------------------------


def get_auth_token() -> str:
    """Token do gate interno (F5.9) — `""` significa **gate aberto** (dev/offline, espinha verde).

    Vem da config (`TAPI_API_TOKEN`, F0.3). É um provider próprio (e não `get_settings()` direto)
    para os testes trocarem por stub e exercitarem aberto/fechado sem depender do `.env` do dev.
    """
    from packages.config import get_settings

    return get_settings().tapi_api_token


def _bearer(authorization: str | None) -> str | None:
    """Extrai o token de um header `Authorization: Bearer <token>` (esquema case-insensitive)."""
    if authorization and authorization[:7].lower() == "bearer ":
        return authorization[7:].strip()
    return None


def require_auth(
    expected: Annotated[str, Depends(get_auth_token)],
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    token: Annotated[str | None, Query()] = None,
) -> None:
    """Gate interno (F5.9): exige o token compartilhado quando há um configurado; senão, passa.

    A ferramenta é interna do gerente de Startups & VCs da NVIDIA Brasil — não é pública (F5.9).
    Sem `TAPI_API_TOKEN` configurado o gate fica **aberto** (dev/offline reproduzível). Com token,
    aceita-o por `Authorization: Bearer <token>`, `X-API-Key: <token>` **ou** `?token=` na query —
    este último porque o SSE (`EventSource`) e o PDF (`<a>`) do front não mandam header (F5.2/F5.8);
    é um trade-off conhecido de ferramenta interna (token pode vazar em log de URL). Comparação em
    tempo constante (`secrets.compare_digest`); `401` com `WWW-Authenticate: Bearer` se não bater.
    """
    if not expected:
        return
    presented = _bearer(authorization) or x_api_key or token
    if not presented or not secrets.compare_digest(presented, expected):
        raise HTTPException(
            status_code=401,
            detail="credencial inválida ou ausente",
            headers={"WWW-Authenticate": "Bearer"},
        )


__all__ = [
    "db_session",
    "get_queue",
    "get_progress_source",
    "get_job_phase",
    "get_briefing_loader",
    "get_trace_loader",
    "get_review_loader",
    "get_langfuse_url",
    "get_auth_token",
    "require_auth",
]
