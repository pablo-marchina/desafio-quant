"""Checkpointer Postgres do grafo (F2.2).

Persiste o estado do grafo por *thread* (= `run_id`) para **resume/retry**: o
LangGraph grava um checkpoint a cada super-step, então um run interrompido (HITL
F2.8) ou que precise de retry de evidência (F2.7) retoma de onde parou em vez de
refazer tudo. Backend = `langgraph-checkpoint-postgres` (`PostgresSaver`).

**Tabelas separadas das do app:** o `PostgresSaver.setup()` cria/migra as tabelas
de checkpoint (`checkpoints`, `checkpoint_writes`, `checkpoint_blobs`, …) por conta
própria — elas **não** entram no `SQLModel.metadata`/Alembic (F0.6), que governa só
as tabelas de domínio (`run`, `company`, …). São dois esquemas de migração distintos
convivendo no mesmo banco.

Uso (worker F2.10 / runs persistidos):
    with postgres_checkpointer() as cp:
        state = run_pipeline("Acme AI", checkpointer=cp)
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from packages.config import get_settings
from packages.schemas import ExecutionMode, HITLMode

if TYPE_CHECKING:
    from packages.schemas import GraphState


def state_serde() -> JsonPlusSerializer:
    """Serializer do checkpoint, fixado em **allow-all** para o nosso `GraphState`.

    O estado carrega `str`-enums (`RunStatus`, `ExecutionMode`, …) e, conforme as fases
    avançam, submodelos Pydantic (`StartupProfile`, `AIMIScore`, `Briefing`) — todos
    (de)serializados pelo caminho de fallback "por módulo" do serde do LangGraph. Com
    `allowed_msgpack_modules=True` ele **permite** esses tipos (emitindo um aviso advisory
    benigno, uma vez por tipo: "será bloqueado numa versão futura").

    Fixamos o `True` **explicitamente** por resiliência: se uma versão futura mudar o
    default para *strict*, o checkpointer continua lendo o nosso estado em vez de bloquear
    silenciosamente profile/aimi/briefing. Uma allowlist restrita resolveria o aviso mas
    viraria *strict* — bloquearia qualquer submodelo ainda não enumerado, frágil enquanto
    o grafo cresce. O checkpoint é dado nosso e confiável (nosso Postgres), então allow-all
    é a semântica correta.

    **`pickle_fallback=True` (2026-06-22, conserto do "não salva"):** o msgpack do serde
    **não** serializa o `HttpUrl` do pydantic (tipo `Url` do pydantic-core) — e ele aparece
    em `RawDocument.url` (scraper, F2.4), `RetrievedChunk.source_url` (RAG) **e** `Evidence.url`
    (toda evidência). Sem o fallback, o checkpoint do 1º super-step (scraper → `raw_docs`)
    estoura `TypeError: Type is not msgpack serializable: RawDocument` → o run **não salva** e o
    stream pra UI quebra (trava no 1º nó). O `pickle_fallback` (de)serializa esses poucos tipos
    não-msgpack via pickle — aceitável porque o checkpoint é interno, confiável e de vida curta
    (resume/retry do mesmo deploy). Conserta os três modelos de uma vez, sem mexer no schema
    da API/DB (trocar `HttpUrl`→`str` em `Evidence` teria ripple largo).
    """
    return JsonPlusSerializer(allowed_msgpack_modules=True, pickle_fallback=True)


def checkpointer_conn_string(url: str | None = None) -> str:
    """URL no formato que o psycopg/langgraph esperam (esquema simples).

    O default vem de `postgres_url` (F0.3) — já é `postgresql://…`. Se vier a forma
    do SQLAlchemy (`postgresql+psycopg://`, usada por engine/Alembic), tira o `+driver`,
    que o `from_conn_string` não aceita.
    """
    raw = url or get_settings().postgres_url
    return raw.replace("postgresql+psycopg://", "postgresql://", 1)


@contextmanager
def postgres_checkpointer(url: str | None = None, *, setup: bool = True) -> Iterator[PostgresSaver]:
    """`PostgresSaver` ligado à config, com as tabelas de checkpoint garantidas.

    `setup=True` roda `PostgresSaver.setup()` (idempotente) — cria/migra as tabelas
    de checkpoint na primeira vez. Desligue (`setup=False`) em hot paths onde o schema
    já existe. Context manager: a conexão fecha ao sair do `with`.
    """
    with PostgresSaver.from_conn_string(checkpointer_conn_string(url)) as saver:
        saver.serde = state_serde()
        if setup:
            saver.setup()
        yield saver


def run_pipeline_persisted(
    query: str,
    *,
    run_id: str | None = None,
    mode: ExecutionMode = ExecutionMode.SINGLE_COMPANY,
    hitl: HITLMode = HITLMode.SYNC,
    url: str | None = None,
) -> GraphState:
    """Roda o grafo com o checkpointer Postgres (resume/retry via `thread_id=run_id`).

    Caminho de produção (worker F2.10). Abre o saver, delega ao `run_pipeline` e fecha
    a conexão ao final. Requer um Postgres no ar — por isso fica fora dos testes offline.
    """
    from .graph import run_pipeline

    with postgres_checkpointer(url) as cp:
        return run_pipeline(query, run_id=run_id, mode=mode, hitl=hitl, checkpointer=cp)
