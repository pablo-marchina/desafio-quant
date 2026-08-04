"""Testes dos briefings terminais (F2.12 dados insuficientes · F2.13 fora de escopo).

Tudo offline/determinista. Exercita:
- `insufficient_data_briefing`: monta o briefing terminal a partir do estado (status
  `dados_insuficientes`, empresa do perfil ou query, lacunas com a contagem de fontes,
  AIMI passado adiante, **sem** recomendação NVIDIA forçada);
- `out_of_scope_briefing` (F2.13): briefing "fora de escopo" para non-AI de alta confiança
  (status `fora_de_escopo`, diagnóstico carregado, **sem** recomendação forçada);
- o nó `briefing` despachando por status: `INSUFFICIENT_DATA` → terminal F2.12, `OUT_OF_SCOPE`
  → terminal F2.13, senão → COMPLETED;
- os **caminhos no grafo**: F2.7→F2.12 (corroboração abaixo do piso + retry esgotado →
  `INSUFFICIENT_DATA`) e F2.7→F2.13 (corroborado + non-AI confiante → `OUT_OF_SCOPE`), ambos
  saltando RAG/recomendação/benchmark — sem alucinar nem forçar recomendação.
"""

from __future__ import annotations

from datetime import UTC, datetime

from packages.agents import (
    compile_graph,
    heuristic_score,
    insufficient_data_briefing,
    out_of_scope_briefing,
)
from packages.agents.nodes import NODES
from packages.schemas import (
    BriefingStatus,
    Claim,
    Classification,
    Evidence,
    GraphState,
    RunStatus,
    StartupProfile,
)

_FETCHED = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)


def _ev(url: str) -> Evidence:
    return Evidence(url=url, snippet="trecho", fetched_at=_FETCHED, content_hash="h")


def _profile(*ev_urls: str, nome: str = "Acme AI") -> StartupProfile:
    return StartupProfile(
        nome=nome,
        descricao=Claim[str](value="o que a empresa faz", evidence=[_ev(u) for u in ev_urls]),
    )


def _non_ai_profile() -> StartupProfile:
    """Perfil claramente non-AI com corroboração (3 hosts) → heurística crava non-AI confiante.

    Sem qualquer termo de IA (descrição/setor) ⇒ `Classification.NON_AI`; 3 fontes distintas +
    2 dimensões ⇒ confiança 0.6 (≥ piso F2.13) e ≥ 2 hosts independentes (corroboração F2.7).
    """
    return StartupProfile(
        nome="Padaria Pão Quente",
        descricao=Claim[str](
            value="rede de padarias artesanais de bairro",
            evidence=[_ev("https://paoquente.com.br/sobre")],
        ),
        setor=Claim[str](
            value="alimentos e bebidas", evidence=[_ev("https://paoquente.com.br/sobre")]
        ),
        source_urls=[
            "https://paoquente.com.br/sobre",
            "https://gazetalocal.com.br/padaria",
            "https://guiadobairro.com.br/paoquente",
        ],
    )


# ----------------------------------------------------- helper: monta o briefing terminal


def test_insufficient_data_briefing_from_profile() -> None:
    state = GraphState(
        run_id="r1",
        query="Acme AI",
        profile=_profile("https://acme.ai/sobre"),
        retry_count=2,
        status=RunStatus.INSUFFICIENT_DATA,
    )
    b = insufficient_data_briefing(state)

    assert b.status is BriefingStatus.DADOS_INSUFICIENTES
    assert b.empresa == "Acme AI"  # nome do perfil, não a query
    assert b.recomendacoes == []  # terminal: nada de recomendação NVIDIA forçada
    assert b.run_id == "r1"
    assert len(b.lacunas) == 1
    lacuna = b.lacunas[0]
    assert "1 fonte" in lacuna  # 1 host independente coletado
    assert "mínimo de 2" in lacuna
    assert "2 retry" in lacuna


def test_insufficient_data_briefing_falls_back_to_query_without_profile() -> None:
    # Defensivo: sem perfil, a empresa é a query e a contagem de fontes é 0.
    state = GraphState(run_id="r2", query="empresa desconhecida")
    b = insufficient_data_briefing(state)
    assert b.empresa == "empresa desconhecida"
    assert b.aimi is None
    assert "0 fonte" in b.lacunas[0]


# --------------------------------------------------------- nó briefing despacha por status


def test_briefing_node_emits_terminal_on_insufficient_data() -> None:
    state = GraphState(
        run_id="r3",
        query="Acme AI",
        profile=_profile("https://acme.ai"),
        status=RunStatus.INSUFFICIENT_DATA,
    )
    update = NODES["briefing"](state)
    assert "status" not in update  # status terminal já vem do evidence_validator
    assert update["briefing"].status is BriefingStatus.DADOS_INSUFICIENTES


def test_briefing_node_completes_on_normal_path() -> None:
    # Caminho normal sem diagnóstico (aimi None): no-op limpo (F4.4) — fecha em COMPLETED, sem
    # briefing terminal nem normal (espinha verde M2). O briefing normal vive em test_briefing.
    state = GraphState(run_id="r4", query="Acme AI", status=RunStatus.RUNNING)
    update = NODES["briefing"](state)
    assert update == {"status": RunStatus.COMPLETED}


# ---------------------------------------- F2.13: briefing "fora de escopo" (non-AI confiante)


def test_out_of_scope_briefing_from_state() -> None:
    profile = _non_ai_profile()
    state = GraphState(
        run_id="r5",
        query="Padaria Pão Quente",
        profile=profile,
        aimi=heuristic_score(profile),
        status=RunStatus.OUT_OF_SCOPE,
    )
    b = out_of_scope_briefing(state)

    assert b.status is BriefingStatus.FORA_DE_ESCOPO
    assert b.empresa == "Padaria Pão Quente"  # nome do perfil
    assert b.recomendacoes == []  # terminal: não força recomendação NVIDIA
    assert b.aimi is not None  # diagnóstico carregado (classe + AIMI baixo com evidência)
    assert b.aimi.classificacao is Classification.NON_AI
    assert b.run_id == "r5"


def test_out_of_scope_briefing_falls_back_to_query_without_profile() -> None:
    # Defensivo: sem perfil, a empresa é a query e o resumo ainda explica o desfecho.
    state = GraphState(run_id="r6", query="empresa qualquer", status=RunStatus.OUT_OF_SCOPE)
    b = out_of_scope_briefing(state)
    assert b.empresa == "empresa qualquer"
    assert b.aimi is None
    assert "fora de escopo" in b.resumo_executivo


def test_briefing_node_emits_terminal_on_out_of_scope() -> None:
    profile = _non_ai_profile()
    state = GraphState(
        run_id="r7",
        query="Padaria Pão Quente",
        profile=profile,
        aimi=heuristic_score(profile),
        status=RunStatus.OUT_OF_SCOPE,
    )
    update = NODES["briefing"](state)
    assert "status" not in update  # status terminal já vem do evidence_validator
    assert update["briefing"].status is BriefingStatus.FORA_DE_ESCOPO


# ------------------------------------------------------- caminho no grafo (F2.7 → F2.12)


def test_graph_routes_to_terminal_when_evidence_insufficient() -> None:
    # Perfil presente com 1 fonte (< piso de 2) e sem orçamento de retry (max_retries=0):
    # o evidence_validator deve saltar ao briefing terminal, pulando RAG/recomendação.
    init = GraphState(
        run_id="run-insuf",
        query="Acme AI",
        profile=_profile("https://acme.ai"),
        max_retries=0,
    )
    out = GraphState.model_validate(compile_graph().invoke(init, {}))

    assert out.status is RunStatus.INSUFFICIENT_DATA
    assert out.briefing is not None
    assert out.briefing.status is BriefingStatus.DADOS_INSUFICIENTES
    assert out.briefing.recomendacoes == []  # não forçou recomendação
    assert out.recommendations == []  # RAG/recommender foram pulados
    assert any("evidência insuficiente" in e for e in out.errors)


def test_graph_routes_to_out_of_scope_when_confident_non_ai() -> None:
    # F2.13: perfil non-AI corroborado (3 hosts) → o classifier crava non-AI confiante e o
    # evidence_validator salta ao briefing terminal "fora de escopo", pulando RAG/recomendação,
    # sem forçar recomendação NVIDIA nem registrar erro (desfecho legítimo).
    init = GraphState(run_id="run-oos", query="Padaria Pão Quente", profile=_non_ai_profile())
    out = GraphState.model_validate(compile_graph().invoke(init, {}))

    assert out.status is RunStatus.OUT_OF_SCOPE
    assert out.briefing is not None
    assert out.briefing.status is BriefingStatus.FORA_DE_ESCOPO
    assert out.briefing.recomendacoes == []  # não forçou recomendação
    assert out.briefing.aimi is not None
    assert out.briefing.aimi.classificacao is Classification.NON_AI
    assert out.recommendations == []  # RAG/recommender foram pulados
    assert out.errors == []  # status, não nota de erro
