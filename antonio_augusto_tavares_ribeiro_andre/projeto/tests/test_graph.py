"""Testes da montagem do grafo multi-agente (F2.1).

Cobrem o que o resto da F2 depende:
- o grafo tem exatamente os 9 nós da ARQUITETURA §3, na espinha dorsal linear;
- compila sem checkpointer (o Postgres é hook da F2.2);
- roda ponta a ponta com nós placeholder e devolve um `GraphState` rascunho (M2),
  preservando run_id/modo/hitl e sem alucinar status.

Tudo offline: os nós da F2.1 são placeholders deterministas (sem rede/LLM).
"""

from __future__ import annotations

from langgraph.graph import END, START

from packages.agents import CONDITIONAL_OUT, PIPELINE, build_graph, compile_graph, run_pipeline
from packages.schemas import ExecutionMode, GraphState, HITLMode, RunStatus


def test_graph_has_exactly_the_pipeline_nodes() -> None:
    nodes = set(build_graph().nodes)
    assert nodes == set(PIPELINE)
    # ordem documentada da ARQUITETURA §3 (search_planner primeiro, briefing último)
    assert PIPELINE[0] == "search_planner"
    assert PIPELINE[-1] == "briefing"


def test_backbone_is_linear() -> None:
    # A espinha segue linear, exceto a saída do evidence_validator, que roteia por Command
    # (F2.7): retry→scraper ou segue→nvidia_rag — logo sem aresta estática de saída.
    expected = {(START, PIPELINE[0]), (PIPELINE[-1], END)}
    expected |= {
        (src, dst)
        for src, dst in zip(PIPELINE, PIPELINE[1:], strict=False)
        if src not in CONDITIONAL_OUT
    }
    assert build_graph().edges == expected


def test_evidence_validator_has_no_static_out_edge() -> None:
    # F2.7: a saída do evidence_validator é condicional (Command goto), não estática.
    edges = build_graph().edges
    assert "evidence_validator" in CONDITIONAL_OUT
    assert not any(src == "evidence_validator" for src, _ in edges)


def test_compile_without_checkpointer() -> None:
    app = compile_graph()
    assert app is not None
    # checkpointer só entra na F2.2; sem ele o grafo ainda compila e roda.
    assert type(app).__name__ == "CompiledStateGraph"


def test_run_pipeline_end_to_end_returns_draft() -> None:
    out = run_pipeline("Acme AI", run_id="run-42")
    assert isinstance(out, GraphState)
    assert out.run_id == "run-42"
    assert out.status is RunStatus.COMPLETED
    # search_planner (F2.3) planeja termos + fontes; a query continua sendo o 1º termo.
    assert out.search_terms[0] == "Acme AI"
    assert out.sources  # fontes priorizadas (§9) não-vazias
    # nada de alucinação nos campos ainda não preenchidos pelos nós reais.
    assert out.profile is None
    assert out.briefing is None
    assert out.errors == []


def test_run_pipeline_generates_run_id_when_absent() -> None:
    out = run_pipeline("fintechs AI em SP")
    assert out.run_id  # uuid gerado


def test_run_pipeline_preserves_mode_and_hitl() -> None:
    out = run_pipeline(
        "fintechs AI em SP",
        mode=ExecutionMode.DISCOVERY,
        hitl=HITLMode.AUTO,
    )
    assert out.mode is ExecutionMode.DISCOVERY
    assert out.hitl is HITLMode.AUTO
