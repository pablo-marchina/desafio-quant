"""Testes do nó human_review (F2.8) — HITL interrupt antes do briefing.

Tudo offline: a pausa humana é opt-in (`hitl_enabled` + modo `state.hitl`, ou `enabled=`).
Exercita:
- `review_payload`: resumo (classe/AIMI/recs) JSON-serializável, sem alucinar campos ausentes;
- o nó **desligado** (default): no-op (`{}`) → espinha verde (M2/DoD);
- modo **auto**: marca `needs_review=True` sem bloquear (sem interrupt);
- modo **sync** (via grafo compilado + InMemorySaver): pausa antes do briefing com o payload
  no interrupt e **retoma** com a decisão humana registrada em `trace` (DoD F2);
- a posição na espinha: `human_review` é estático entre gpu_benchmark e briefing.
"""

from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

import packages.agents.human_review as hr
from packages.agents import (
    CONDITIONAL_OUT,
    PIPELINE,
    build_graph,
    compile_graph,
    review_payload,
)
from packages.agents.checkpoint import state_serde
from packages.agents.nodes import human_review
from packages.schemas import (
    AIMIScore,
    Classification,
    GraphState,
    HITLMode,
    PillarScore,
    RunStatus,
    StartupProfile,
)
from packages.schemas.enums import AIMIPillar

# O serde allow-all emite um aviso advisory benigno por tipo (ver `state_serde`).
pytestmark = pytest.mark.filterwarnings("ignore:Deserializing unregistered type")


class _FakeSettings:
    def __init__(self, *, enabled: bool) -> None:
        self.hitl_enabled = enabled


def _cfg(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _aimi(classe: Classification = Classification.AI_NATIVE) -> AIMIScore:
    # 4 pilares <=6 dispensam evidência (RUBRICA §0); só precisamos de um AIMI válido.
    def _p(pilar: AIMIPillar) -> PillarScore:
        return PillarScore(pilar=pilar, score=5, justificativa="sinal mínimo")

    return AIMIScore(
        data_moat=_p(AIMIPillar.DATA_MOAT),
        workflow_depth=_p(AIMIPillar.WORKFLOW_DEPTH),
        technical_optimization=_p(AIMIPillar.TECHNICAL_OPTIMIZATION),
        distribution_moat=_p(AIMIPillar.DISTRIBUTION_MOAT),
        classificacao=classe,
    )


# --- review_payload -----------------------------------------------------------


def test_review_payload_summarizes_diagnosis() -> None:
    state = GraphState(
        run_id="r1",
        query="Acme AI",
        profile=StartupProfile(nome="Acme AI"),
        aimi=_aimi(),
    )
    payload = review_payload(state)
    assert payload["run_id"] == "r1"
    assert payload["query"] == "Acme AI"
    assert payload["empresa"] == "Acme AI"
    assert payload["classificacao"] == "AI-native"
    assert payload["aimi_total"] == 20  # 4 × 5
    assert payload["recomendacoes"] == []  # vazias até a F4


def test_review_payload_does_not_hallucinate_when_empty() -> None:
    # run offline (sem extração/classificação): campos viram None/[] em vez de alucinar.
    payload = review_payload(GraphState(run_id="r1", query="Acme"))
    assert payload["empresa"] is None
    assert payload["classificacao"] is None
    assert payload["aimi_total"] is None
    assert payload["recomendacoes"] == []


# --- nó desligado (default offline) -------------------------------------------


def test_node_disabled_via_param_is_noop() -> None:
    state = GraphState(run_id="r1", query="Acme", hitl=HITLMode.SYNC)
    assert human_review(state, enabled=False) == {}


def test_node_disabled_by_default_settings_is_noop(monkeypatch) -> None:
    # hitl_enabled off (default) → no-op mesmo em modo sync (espinha verde, M2/DoD).
    monkeypatch.setattr(hr, "get_settings", lambda: _FakeSettings(enabled=False))
    state = GraphState(run_id="r1", query="Acme", hitl=HITLMode.SYNC)
    assert human_review(state) == {}


# --- modo auto: marca sem bloquear --------------------------------------------


def test_node_auto_marks_review_without_blocking() -> None:
    # auto não chama interrupt (não levanta) — só sinaliza needs_review p/ revisão assíncrona.
    state = GraphState(run_id="r1", query="fintechs AI em SP", hitl=HITLMode.AUTO)
    assert human_review(state, enabled=True) == {"needs_review": True}


def test_auto_run_completes_and_marks(monkeypatch) -> None:
    # grafo ponta a ponta no modo auto + habilitado: completa (não pausa) e fica marcado.
    monkeypatch.setattr(hr, "get_settings", lambda: _FakeSettings(enabled=True))
    from packages.agents import run_pipeline

    out = run_pipeline("fintechs AI em SP", hitl=HITLMode.AUTO)
    assert out.status is RunStatus.COMPLETED
    assert out.needs_review is True


# --- modo sync: interrupt + resume (via grafo + checkpointer) ------------------


def test_sync_interrupts_before_briefing_then_resumes(monkeypatch) -> None:
    monkeypatch.setattr(hr, "get_settings", lambda: _FakeSettings(enabled=True))
    app = compile_graph(checkpointer=InMemorySaver(serde=state_serde()))
    cfg = _cfg("run-hitl")
    app.invoke(GraphState(run_id="run-hitl", query="Acme AI", hitl=HITLMode.SYNC), cfg)

    paused = app.get_state(cfg)
    assert paused.next == ("human_review",)  # pausou antes do briefing
    assert paused.values["status"] is RunStatus.RUNNING  # ainda não concluiu
    # o payload de revisão chega ao humano pelo interrupt pendente
    interrupts = paused.tasks[0].interrupts
    assert interrupts and interrupts[0].value["query"] == "Acme AI"

    decision = {"approved": True, "nota": "diagnóstico ok"}
    app.invoke(Command(resume=decision), cfg)  # retoma com a decisão humana
    resumed = app.get_state(cfg)
    assert resumed.next == ()  # terminou
    assert resumed.values["status"] is RunStatus.COMPLETED
    assert resumed.values["trace"]["human_review"] == decision
    assert resumed.values["needs_review"] is False  # sync não usa o marcador do auto


# --- posição na espinha -------------------------------------------------------


def test_human_review_is_static_node_before_briefing() -> None:
    assert PIPELINE[-1] == "briefing"
    assert PIPELINE[-2] == "human_review"
    assert "human_review" not in CONDITIONAL_OUT  # saída estática, não roteia por Command
    edges = build_graph().edges
    assert ("gpu_benchmark", "human_review") in edges
    assert ("human_review", "briefing") in edges
