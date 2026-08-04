"""Testes do nó recommender (F4.2/F4.3) — gaps do AIMI × evidência NVIDIA → Recommendation 2 lados.

Offline/determinista. Exercita:

1. **Espinha determinista** (`build_recommendations`): cruza as candidatas (F4.1) × citações (F3.7)
   por `kb_tech`; emite só com **evidência dos dois lados**; descarta candidata sem citação NVIDIA;
   datada pelo snapshot do manifesto (sem `now()`); determinística.
2. **Evidência de gap**: pilar-gap com evidência usa-a; gap de ausência (P3 wrapper, score ≤6) cai
   no perfil público; tech de setor ancora no domínio declarado (§5.5).
3. **Caminho LLM** (`recommend_with_llm`/`make_recommendations`): refina a redação **preservando a
   evidência**; degrada para a espinha a qualquer falha de JSON.
4. **O nó** (`recommender`): no-op limpo sem `aimi` (espinha verde M2); sem evidência não recomenda;
   ponta a ponta sobre o RAG real (`nvidia_rag` → `recommender`) com os dois lados em cada item.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from packages.agents import match_techs
from packages.agents.classifier import heuristic_score
from packages.agents.nvidia_rag import nvidia_rag
from packages.agents.recommender import (
    build_recommendations,
    make_recommendations,
    recommend_with_llm,
    recommender,
)
from packages.rag import load_kb_sources
from packages.schemas import (
    MAX_SCORE_WITHOUT_EVIDENCE,
    AIMIPillar,
    AIMIScore,
    Claim,
    Classification,
    Evidence,
    GraphState,
    PillarScore,
    Priority,
    Product,
    RetrievedChunk,
    StartupProfile,
    Technology,
)

_FETCHED = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)
#: Todas as fontes do manifesto (F3.1) têm este snapshot — a `Evidence` NVIDIA é datada por ele.
_KB_CAPTURED = datetime(2026, 6, 7, tzinfo=UTC)


def _ev(url: str = "https://startup.example", snippet: str = "trecho público") -> Evidence:
    return Evidence(url=url, snippet=snippet, fetched_at=_FETCHED, content_hash="h1")


def _claim(value: str) -> Claim[str]:
    return Claim[str](value=value, evidence=[_ev()])


def _pillar(pilar: AIMIPillar, score: int) -> PillarScore:
    ev = [_ev()] if score > MAX_SCORE_WITHOUT_EVIDENCE else []
    return PillarScore(pilar=pilar, score=score, justificativa="teste", evidencia=ev)


def _aimi(p1: int, p2: int, p3: int, p4: int) -> AIMIScore:
    return AIMIScore(
        data_moat=_pillar(AIMIPillar.DATA_MOAT, p1),
        workflow_depth=_pillar(AIMIPillar.WORKFLOW_DEPTH, p2),
        technical_optimization=_pillar(AIMIPillar.TECHNICAL_OPTIMIZATION, p3),
        distribution_moat=_pillar(AIMIPillar.DISTRIBUTION_MOAT, p4),
        classificacao=Classification.AI_NATIVE,
    )


def _profile(
    *, descricao: str | None = None, setor: str | None = None, tech: str | None = None
) -> StartupProfile:
    return StartupProfile(
        nome="ACME",
        descricao=_claim(descricao) if descricao is not None else None,
        setor=_claim(setor) if setor is not None else None,
        tecnologias=(
            [Technology(nome=tech, categoria="LLM", uso="via api", evidence=[_ev()])]
            if tech is not None
            else []
        ),
    )


def _kb_source(tech: str):
    for s in load_kb_sources():
        if s.tech == tech and s.source_type == "doc":
            return s
    raise AssertionError(f"sem fonte doc na KB p/ {tech!r}")


def _chunk(tech: str, *, idx: int = 0, score: float = 0.9) -> RetrievedChunk:
    """Citação recuperada (F3.7) p/ uma tech — chunk_id real (manifesto) p/ a data resolver."""
    s = _kb_source(tech)
    return RetrievedChunk(
        text=f"{tech}: trecho citável da KB NVIDIA.",
        source_url=s.url,
        source_title=s.title,
        score=score,
        metadata={"chunk_id": f"{s.id}::{idx:02d}", "tech": tech, "source_type": "doc"},
    )


def _healthcare_wrapper() -> StartupProfile:
    """AI-native de saúde dependente de API externa → P3 baixo (gap) + setor saúde (§5.5)."""
    return StartupProfile(
        nome="MediChat",
        descricao=_claim(
            "Assistente de IA para clínicas: usa a API da OpenAI para responder dúvidas "
            "de pacientes e apoiar diagnóstico em saúde."
        ),
        setor=_claim("Saúde / healthtech"),
        produtos=[Product(nome="Assistente", descricao="chat de saúde", evidence=[_ev()])],
        tecnologias=[
            Technology(nome="OpenAI API", categoria="LLM provider", uso="via api", evidence=[_ev()])
        ],
        source_urls=["https://startup.example", "https://news.example"],
    )


# --- Espinha determinista: cruzamento candidata × citação ------------------------------------


def test_pillar_gap_recommendation_carries_both_sides_and_kb_date() -> None:
    # P3 gap severo (wrapper de API) + citação de NIM → graduação API→stack com evidência 2 lados.
    aimi = _aimi(20, 20, 4, 22)
    profile = _profile(descricao="assistente que usa a API da OpenAI", tech="OpenAI API")
    recs = build_recommendations(aimi, profile, [_chunk("NVIDIA NIM")])
    assert [r.tech for r in recs] == ["NVIDIA NIM"]  # só a tech com citação casada
    nim = recs[0]
    assert nim.pilar_origem is AIMIPillar.TECHNICAL_OPTIMIZATION  # rastreabilidade gap→tech
    assert nim.evidencia_gap and nim.evidencia_nvidia  # invariante dos dois lados (F4.5)
    # lado NVIDIA datado pelo snapshot curado do manifesto (determinístico, não now()).
    assert nim.evidencia_nvidia[0].fetched_at == _KB_CAPTURED


def test_gap_evidence_uses_pillar_when_it_has_evidence() -> None:
    # P3=10 é gap (≤12) E tem evidência (>6): o lado-startup vem do pilar, não do fallback.
    aimi = _aimi(20, 20, 10, 22)
    recs = build_recommendations(aimi, _profile(), [_chunk("NVIDIA NIM")])
    nim = next(r for r in recs if r.tech == "NVIDIA NIM")
    assert nim.evidencia_gap == aimi.technical_optimization.evidencia


def test_severe_gap_without_pillar_evidence_falls_back_to_profile() -> None:
    # P3=4 (ausente, sem evidência no pilar) → o lado-startup ancora no perfil público (descrição).
    aimi = _aimi(20, 20, 4, 22)
    profile = _profile(descricao="100% sobre API externa", tech="OpenAI API")
    nim = next(r for r in build_recommendations(aimi, profile, [_chunk("NVIDIA NIM")]))
    assert nim.evidencia_gap  # não cai por falta do lado-startup (recomendação mais valiosa)
    assert all(isinstance(e, Evidence) for e in nim.evidencia_gap)


def test_candidate_without_nvidia_citation_is_dropped() -> None:
    # Gap de P3 (NIM/TensorRT/Triton), mas a única citação é de Riva → nada casa → sem recomendação.
    aimi = _aimi(20, 20, 4, 22)
    profile = _profile(descricao="usa API externa", tech="OpenAI API")
    assert build_recommendations(aimi, profile, [_chunk("NVIDIA Riva")]) == []


def test_no_retrieval_yields_no_recommendations() -> None:
    # Sem evidência NVIDIA recuperada não há recomendação (não alucina o lado direito).
    aimi = _aimi(20, 20, 4, 22)
    assert build_recommendations(aimi, _profile(descricao="x", tech="y"), []) == []


def test_sector_recommendation_grounds_gap_in_domain() -> None:
    # §5.5: saúde → Clara/MONAI; o gap (lado-startup) ancora no domínio declarado (setor/descrição).
    aimi = _aimi(20, 20, 20, 22)
    profile = _profile(setor="Healthtech / saúde", descricao="diagnóstico clínico")
    recs = build_recommendations(aimi, profile, [_chunk("NVIDIA Clara"), _chunk("MONAI", idx=1)])
    techs = {r.tech for r in recs}
    assert {"NVIDIA Clara", "MONAI"} <= techs
    clara = next(r for r in recs if r.tech == "NVIDIA Clara")
    assert clara.pilar_origem is None  # tech de setor (sem pilar de origem)
    assert clara.evidencia_gap and clara.evidencia_nvidia


def test_build_recommendations_is_deterministic() -> None:
    aimi = _aimi(20, 20, 4, 22)
    profile = _profile(setor="saúde", descricao="usa API", tech="OpenAI API")
    chunks = [_chunk("NVIDIA NIM"), _chunk("NVIDIA Clara", idx=1)]
    first = build_recommendations(aimi, profile, chunks)
    assert first == build_recommendations(aimi, profile, chunks)


# --- Caminho LLM (refino plugável, fallback) -------------------------------------------------


def test_llm_refines_text_but_preserves_evidence() -> None:
    aimi = _aimi(20, 20, 10, 22)
    base = build_recommendations(aimi, _profile(), [_chunk("NVIDIA NIM")])
    assert base
    raw = json.dumps(
        [
            {
                "tech": "NVIDIA NIM",
                "justificativa_tecnica": "REFINADA tecnica",
                "justificativa_negocio": "REFINADA negocio",
                "proxima_acao": "REFINADA acao",
                "prioridade": "media",
            }
        ]
    )
    refined = recommend_with_llm(base, recommend=lambda _s: raw)
    assert refined is not None
    nim = refined[0]
    assert nim.justificativa_tecnica == "REFINADA tecnica"
    assert nim.proxima_acao == "REFINADA acao"
    assert nim.prioridade is Priority.MEDIA
    # a evidência dos dois lados é a determinista — o LLM refina a redação, não a proveniência.
    assert nim.evidencia_gap == base[0].evidencia_gap
    assert nim.evidencia_nvidia == base[0].evidencia_nvidia


def test_llm_falls_back_to_none_on_bad_json() -> None:
    base = build_recommendations(_aimi(20, 20, 10, 22), _profile(), [_chunk("NVIDIA NIM")])
    assert recommend_with_llm(base, recommend=lambda _s: "isto nao e json") is None


def test_llm_ignores_unknown_tech_and_keeps_unrefined_skeletons() -> None:
    base = build_recommendations(_aimi(20, 20, 10, 22), _profile(), [_chunk("NVIDIA NIM")])
    raw = json.dumps([{"tech": "Tech Inexistente", "justificativa_tecnica": "x"}])
    assert recommend_with_llm(base, recommend=lambda _s: raw) == base  # esqueletos intactos


def test_make_recommendations_default_is_deterministic_skeleton() -> None:
    aimi = _aimi(20, 20, 10, 22)
    chunks = [_chunk("NVIDIA NIM")]
    # sem adapter e com o flag off (default) → espinha determinista (== build_recommendations).
    assert make_recommendations(aimi, _profile(), chunks) == build_recommendations(
        aimi, _profile(), chunks
    )


def test_make_recommendations_uses_injected_adapter() -> None:
    aimi = _aimi(20, 20, 10, 22)
    raw = json.dumps([{"tech": "NVIDIA NIM", "proxima_acao": "ACAO REFINADA"}])
    recs = make_recommendations(aimi, _profile(), [_chunk("NVIDIA NIM")], recommend=lambda _s: raw)
    assert recs[0].proxima_acao == "ACAO REFINADA"


# --- O nó -----------------------------------------------------------------------------------


def test_node_is_noop_without_diagnosis() -> None:
    # Espinha offline sem classificação (aimi None): nada a recomendar → no-op limpo (M2/DoD).
    assert recommender(GraphState(run_id="x", query="q")) == {}


def test_node_without_evidence_makes_no_recommendation() -> None:
    profile = _healthcare_wrapper()
    aimi = heuristic_score(profile)
    # aimi presente mas retrieved vazio → sem recomendação (não alucina sem o lado NVIDIA).
    assert recommender(GraphState(run_id="x", query="q", profile=profile, aimi=aimi)) == {}


def test_node_end_to_end_over_real_rag() -> None:
    profile = _healthcare_wrapper()
    aimi = heuristic_score(profile)
    rag = nvidia_rag(GraphState(run_id="r", query="x", profile=profile, aimi=aimi))
    state = GraphState(
        run_id="r", query="x", profile=profile, aimi=aimi, retrieved=rag["retrieved"]
    )
    update = recommender(state)
    recs = update["recommendations"]
    assert recs  # saúde + wrapper de API ⇒ ao menos uma tech recuperada casa uma candidata
    cand_techs = {c.rule.tech for c in match_techs(aimi, profile)}
    for r in recs:
        assert r.evidencia_gap and r.evidencia_nvidia  # dois lados em cada recomendação (F4.5)
        assert r.tech in cand_techs  # só recomenda candidata das regras (F4.1)
    assert update["trace"]["recommender"]["n"] == len(recs)
    assert update["trace"]["recommender"]["techs"] == [r.tech for r in recs]
