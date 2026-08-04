"""Testes do checkpointer Postgres do grafo (F2.2).

Cobrem o que a F2 promete no DoD ("run interrompido e retomado via checkpoint"):
- a URL é normalizada p/ o esquema que o psycopg/langgraph esperam;
- o serde allow-all faz round-trip do `GraphState` (enums + submodelos Pydantic);
- `run_pipeline(checkpointer=...)` persiste por `thread_id=run_id`;
- interrupt + resume retomam do checkpoint sem refazer o que já rodou.

O mecanismo é testado offline com `InMemorySaver` (mesmo serde do Postgres). O
caminho Postgres real fica num teste de integração que **pula** sem banco no ar —
espelha o padrão dos smokes de rede (F0.7/F1.2).
"""

from __future__ import annotations

import psycopg
import pytest
from langgraph.checkpoint.memory import InMemorySaver

from packages.agents import build_graph, run_pipeline
from packages.agents.checkpoint import (
    checkpointer_conn_string,
    postgres_checkpointer,
    state_serde,
)
from packages.schemas import GraphState, RunStatus, StartupProfile

# O serde allow-all emite um aviso advisory benigno por tipo (ver `state_serde`);
# silenciamos só neste módulo p/ manter a saída limpa sem mascarar outros avisos.
pytestmark = pytest.mark.filterwarnings("ignore:Deserializing unregistered type")


def _cfg(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


# --- URL / serde --------------------------------------------------------------


def test_conn_string_normalizes_sqlalchemy_driver() -> None:
    # a forma do SQLAlchemy (engine/Alembic) tem +psycopg; o saver quer o esquema simples
    assert (
        checkpointer_conn_string("postgresql+psycopg://u:p@h:5432/db")
        == "postgresql://u:p@h:5432/db"
    )
    assert checkpointer_conn_string().startswith("postgresql://")


def test_state_serde_roundtrips_enums_and_submodels() -> None:
    serde = state_serde()
    state = GraphState(
        run_id="r1",
        query="Acme AI",
        status=RunStatus.RUNNING,
        profile=StartupProfile(nome="Acme AI"),
    )
    restored = serde.loads_typed(serde.dumps_typed(state))
    assert restored == state
    assert restored.status is RunStatus.RUNNING
    assert restored.profile is not None and restored.profile.nome == "Acme AI"


def test_state_serde_roundtrips_httpurl_models() -> None:
    # Regressão (2026-06-22): RawDocument.url / RetrievedChunk.source_url são HttpUrl (tipo `Url` do
    # pydantic-core), que o msgpack do serde NÃO serializa. Sem o `pickle_fallback` o checkpoint do
    # 1º super-step (scraper → raw_docs) estoura `TypeError: ... not msgpack serializable:
    # RawDocument` e o run "não salva". Os testes offline não pegavam (scraper no-op → raw_docs []).
    from datetime import UTC, datetime

    from packages.schemas import RawDocument, RetrievedChunk

    serde = state_serde()
    state = GraphState(
        run_id="r-url",
        query="rivio.ai",
        raw_docs=[
            RawDocument(
                url="https://rivio.ai",
                content="conteúdo bruto",
                fetched_at=datetime(2026, 1, 2, tzinfo=UTC),
                source_type="firecrawl",
            )
        ],
        retrieved=[RetrievedChunk(text="trecho NVIDIA", source_url="https://build.nvidia.com/nim")],
    )
    restored = serde.loads_typed(serde.dumps_typed(state))
    assert restored == state  # roundtrip exato (HttpUrl inclusive)
    assert str(restored.raw_docs[0].url) == "https://rivio.ai/"
    assert str(restored.retrieved[0].source_url) == "https://build.nvidia.com/nim"


def test_state_serde_roundtrips_profile_with_generic_claims() -> None:
    # Regressão (2026-06-25, ao vivo na rivio.ai): o `profile` é cheio de `Claim[str]`/`Claim[int]`
    # (genéricos parametrizados). O pickle_fallback do serde estourava `PicklingError: Can't pickle
    # Claim[str]` (qualname não existe no módulo) ao persistir o estado no **interrupt do HITL**
    # (F2.8) — o perfil só chega lá quando a extração produz dados. O `Claim.__reduce__` picla pela
    # base + dados, destravando o checkpoint do HITL (a review HITL vinha em branco sem isto).
    from datetime import UTC, datetime

    from packages.schemas import Evidence, StartupProfile
    from packages.schemas.evidence import Claim

    _at = datetime(2026, 1, 2, tzinfo=UTC)
    ev = Evidence(url="https://rivio.ai", snippet="o que faz", fetched_at=_at)
    profile = StartupProfile(
        nome="Rivio",
        descricao=Claim[str](value="plataforma de X", evidence=[ev], confidence=0.9),
        ano_fundacao=Claim[int](value=2021, evidence=[ev]),
        source_urls=["https://rivio.ai"],
    )
    serde = state_serde()
    state = GraphState(run_id="r-claim", query="rivio.ai", profile=profile)
    restored = serde.loads_typed(serde.dumps_typed(state))
    assert restored.profile is not None
    assert restored.profile.descricao.value == "plataforma de X"
    assert restored.profile.descricao.is_grounded
    assert restored.profile.ano_fundacao.value == 2021


# --- wiring com run_pipeline --------------------------------------------------


def test_run_pipeline_persists_under_run_id_as_thread() -> None:
    cp = InMemorySaver(serde=state_serde())
    out = run_pipeline("Acme AI", run_id="run-1", checkpointer=cp)
    assert out.status is RunStatus.COMPLETED
    # o checkpoint foi gravado na thread = run_id (contrato p/ resume/worker F2.10)
    saved = cp.get_tuple(_cfg("run-1"))
    assert saved is not None


# --- interrupt + resume via checkpoint (DoD F2) -------------------------------


def test_interrupt_and_resume_via_checkpoint() -> None:
    # interrupt_before sintético (o HITL real é F2.8) só p/ exercitar o checkpoint.
    app = build_graph().compile(
        checkpointer=InMemorySaver(serde=state_serde()),
        interrupt_before=["briefing"],
    )
    cfg = _cfg("run-2")
    app.invoke(GraphState(run_id="run-2", query="Acme AI"), cfg)

    paused = app.get_state(cfg)
    assert paused.next == ("briefing",)  # parou antes do briefing
    assert paused.values["status"] is RunStatus.RUNNING  # ainda não concluiu

    app.invoke(None, cfg)  # retoma do checkpoint
    resumed = app.get_state(cfg)
    assert resumed.next == ()  # terminou
    assert resumed.values["status"] is RunStatus.COMPLETED


# --- integração Postgres real (pula sem banco) --------------------------------


def test_postgres_checkpointer_setup_and_roundtrip() -> None:
    # connect_timeout curto p/ pular rápido quando não há banco no ar (sem ele, conectar
    # a uma porta fechada pode esperar segundos antes de falhar, travando a suíte).
    url = checkpointer_conn_string() + "?connect_timeout=3"
    try:
        with postgres_checkpointer(url) as cp:
            app = build_graph().compile(checkpointer=cp)
            cfg = _cfg("run-pg-1")
            app.invoke(GraphState(run_id="run-pg-1", query="Acme AI"), cfg)
            snapshot = app.get_state(cfg)
    except psycopg.OperationalError as exc:  # sem Postgres no ar
        pytest.skip(f"Postgres indisponível: {exc}")
    assert snapshot.values["status"] is RunStatus.COMPLETED
