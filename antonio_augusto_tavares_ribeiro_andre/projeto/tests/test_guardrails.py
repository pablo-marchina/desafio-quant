"""Testes do rail de evidência do briefing (F4.5) — NeMo Guardrails: recomendação só com 2 lados.

Offline/determinista. Exercita:

1. **Núcleo** (`evidence_violations`): aprova rec com os dois lados; flagra `evidencia_gap` ausente,
   `evidencia_nvidia` ausente, e ambos.
2. **Espinha** (`check_recommendations`): separa aprovadas × bloqueadas preservando a ordem; o
   `GuardrailReport` (`passou`, `trace()`) reporta os motivos.
3. **Seam plugável** (`guard_recommendations`): default determinista; `guard=` injetado tem
   precedência; com o flag ligado e sem `nemoguardrails` (Windows) cai na espinha (fallback).
4. **O nó** (`briefing`): descarta a recomendação sem os dois lados **antes** do texto e carimba
   `trace["guardrails"]`; mantém a recomendação válida.
5. **Config NeMo**: o diretório `guardrails_config/` (Colang + actions) existe (artefato de prod).
"""

from __future__ import annotations

from datetime import UTC, datetime

from packages.agents import (
    BlockedRecommendation,
    GuardrailReport,
    check_recommendations,
    evidence_violations,
    guard_recommendations,
)
from packages.agents import guardrails as gr
from packages.agents.briefing import briefing
from packages.schemas import (
    Complexity,
    Evidence,
    GraphState,
    Priority,
    Recommendation,
    RunStatus,
)

_FETCHED = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)


def _ev(url: str = "https://startup.example", snippet: str = "trecho público") -> Evidence:
    return Evidence(url=url, snippet=snippet, fetched_at=_FETCHED, content_hash="h1")


def _rec(tech: str = "NVIDIA NIM", prioridade: Priority = Priority.ALTA) -> Recommendation:
    """Recomendação **válida** (os dois lados) — passa pela validação do schema (F0.5)."""
    return Recommendation(
        tech=tech,
        justificativa_tecnica="téc",
        justificativa_negocio="neg",
        prioridade=prioridade,
        complexidade=Complexity.MEDIA,
        proxima_acao="Provisionar e medir.",
        evidencia_gap=[_ev()],
        evidencia_nvidia=[_ev(url="https://docs.nvidia.com/nim", snippet="NVIDIA NIM")],
    )


def _invalid(tech: str = "FANTASMA", *, gap: bool = True, nvidia: bool = True) -> Recommendation:
    """Recomendação que **burla** a validação do schema (`model_construct`) — simula alucinação.

    Com `gap=False`/`nvidia=False` um lado de evidência fica vazio: o construtor normal levantaria
    (`_require_both_sides`, F0.5), mas `model_construct` não valida — exatamente o que o rail pega.
    """
    return Recommendation.model_construct(
        tech=tech,
        justificativa_tecnica="téc",
        justificativa_negocio="neg",
        prioridade=Priority.ALTA,
        complexidade=Complexity.MEDIA,
        proxima_acao="—",
        pilar_origem=None,
        evidencia_gap=[_ev()] if gap else [],
        evidencia_nvidia=[_ev(url="https://docs.nvidia.com/x")] if nvidia else [],
        roi=None,
    )


# --- Núcleo: evidence_violations --------------------------------------------------------------


def test_violations_empty_for_full_recommendation() -> None:
    assert evidence_violations(_rec()) == []


def test_violations_flag_missing_gap_side() -> None:
    assert evidence_violations(_invalid(gap=False)) == [gr.GAP_MISSING]


def test_violations_flag_missing_nvidia_side() -> None:
    assert evidence_violations(_invalid(nvidia=False)) == [gr.NVIDIA_MISSING]


def test_violations_flag_both_sides_missing() -> None:
    assert evidence_violations(_invalid(gap=False, nvidia=False)) == [
        gr.GAP_MISSING,
        gr.NVIDIA_MISSING,
    ]


# --- Espinha: check_recommendations -----------------------------------------------------------


def test_check_splits_allowed_and_blocked_preserving_order() -> None:
    ok1, bad, ok2 = _rec("NIM"), _invalid("FANTASMA", nvidia=False), _rec("Triton")
    report = check_recommendations([ok1, bad, ok2])

    assert report.aprovadas == [ok1, ok2]  # ordem preservada
    assert not report.passou
    assert report.bloqueadas == [
        BlockedRecommendation(tech="FANTASMA", motivos=[gr.NVIDIA_MISSING])
    ]


def test_check_all_valid_passes() -> None:
    report = check_recommendations([_rec("NIM"), _rec("Triton")])
    assert report.passou
    assert report.bloqueadas == []
    assert report.trace() == {"n_aprovadas": 2, "n_bloqueadas": 0, "bloqueadas": []}


def test_check_empty_is_a_clean_pass() -> None:
    report = check_recommendations([])
    assert report.passou
    assert report.aprovadas == []


def test_report_trace_is_serializable_with_reasons() -> None:
    report = check_recommendations([_invalid("X", gap=False)])
    trace = report.trace()
    assert trace["n_aprovadas"] == 0 and trace["n_bloqueadas"] == 1
    assert trace["bloqueadas"][0] == {"tech": "X", "motivos": [gr.GAP_MISSING]}


# --- Seam plugável: guard_recommendations -----------------------------------------------------


def test_guard_default_is_deterministic_spine() -> None:
    recs = [_rec("NIM"), _invalid("X", gap=False)]
    assert guard_recommendations(recs) == check_recommendations(recs)


def test_injected_guard_takes_precedence() -> None:
    sentinel = GuardrailReport(aprovadas=[], bloqueadas=[])
    assert guard_recommendations([_rec("NIM")], guard=lambda _r: sentinel) is sentinel


def test_flag_on_falls_back_to_spine_without_nemoguardrails(monkeypatch) -> None:
    # Flag ligado mas nemoguardrails ausente (Windows) ⇒ _nemo_guard levanta → cai na espinha.
    fake = type("S", (), {"briefing_use_guardrails": True})()
    monkeypatch.setattr(gr, "get_settings", lambda: fake)
    recs = [_rec("NIM"), _invalid("X", nvidia=False)]
    report = guard_recommendations(recs)
    assert report.aprovadas == [recs[0]]
    assert [b.tech for b in report.bloqueadas] == ["X"]


# --- O nó briefing ----------------------------------------------------------------------------


def _aimi():
    # AIMI mínimo válido p/ o caminho normal do nó (gap em P3 ⇒ alvo de graduação).
    from packages.schemas import AIMIPillar, AIMIScore, Classification, PillarScore

    def p(pilar, score):
        return PillarScore(pilar=pilar, score=score, justificativa="t", evidencia=[])

    return AIMIScore(
        data_moat=p(AIMIPillar.DATA_MOAT, 5),
        workflow_depth=p(AIMIPillar.WORKFLOW_DEPTH, 5),
        technical_optimization=p(AIMIPillar.TECHNICAL_OPTIMIZATION, 4),
        distribution_moat=p(AIMIPillar.DISTRIBUTION_MOAT, 5),
        classificacao=Classification.AI_NATIVE,
    )


def test_node_drops_unsupported_recommendation_and_stamps_trace() -> None:
    # GraphState revalida a lista (defesa extra) — monta válido e injeta a rec alucinada na lista.
    state = GraphState(run_id="r", query="ACME", aimi=_aimi(), recommendations=[_rec("NVIDIA NIM")])
    state.recommendations.append(_invalid("FANTASMA", nvidia=False))
    update = briefing(state)

    assert update["status"] is RunStatus.COMPLETED
    techs = [r.tech for r in update["briefing"].recomendacoes]
    assert techs == ["NVIDIA NIM"]  # a sem evidência NVIDIA foi barrada (não vira texto)
    g = update["trace"]["guardrails"]
    assert g["n_aprovadas"] == 1 and g["n_bloqueadas"] == 1
    assert g["bloqueadas"][0]["tech"] == "FANTASMA"


def test_node_uses_injected_guard() -> None:
    # Rail injetado bloqueando tudo ⇒ briefing sai sem recomendação (honesto), sem alucinar.
    state = GraphState(run_id="r", query="ACME", aimi=_aimi(), recommendations=[_rec("NVIDIA NIM")])
    update = briefing(state, guard=lambda _r: GuardrailReport(aprovadas=[], bloqueadas=[]))
    assert update["briefing"].recomendacoes == []
    assert update["trace"]["guardrails"]["n_aprovadas"] == 0


# --- Config NeMo (artefato de produção) -------------------------------------------------------


def test_nemo_guardrails_config_is_shipped() -> None:
    # A orquestração de produção (Colang + actions) existe; carregada no container (_nemo_guard).
    assert (gr.GUARDRAILS_CONFIG / "config.yml").is_file()
    assert (gr.GUARDRAILS_CONFIG / "rails.co").is_file()
    assert (gr.GUARDRAILS_CONFIG / "actions.py").is_file()
