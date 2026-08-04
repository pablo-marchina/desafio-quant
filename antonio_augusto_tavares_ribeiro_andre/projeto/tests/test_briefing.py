"""Testes do nó briefing (F4.4) — perfil + AIMI + recomendações → relatório executivo PT-BR.

Offline/determinista. Exercita:

1. **Espinha determinista** (`build_briefing`): status NORMAL, empresa do perfil/query, resumo
   aterrado (classe + AIMI + principal gap), os **três eixos** do §2, recomendações carregadas;
   `acao_comercial` ramifica pela região do plano (alvo de graduação / maduro / nutrição);
   `acao_tecnica` ancorada na recomendação de maior prioridade; determinismo.
2. **Markdown** (`render_markdown`): a view PT-BR do JSON — cabeçalhos, bloco AIMI, recomendações
   com evidência dos dois lados, os três eixos e as lacunas (variante terminal).
3. **Caminho LLM** (`refine_with_llm`/`make_briefing`): refina a redação **preservando diagnóstico
   e recomendações**; degrada para a espinha a qualquer falha de JSON.
4. **O nó** (`briefing`): despacha terminais (F2.12/F2.13); no-op limpo sem `aimi` (espinha verde
   M2, fecha em COMPLETED sem briefing); caminho normal emite briefing + COMPLETED; ponta a ponta
   sobre o grafo real (perfil → ... → briefing normal com recomendação e os três eixos).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from packages.agents import (
    build_briefing,
    compile_graph,
    heuristic_score,
    make_briefing,
    refine_with_llm,
    render_markdown,
    render_pdf,
)
from packages.agents.briefing import briefing
from packages.agents.nvidia_rag import nvidia_rag
from packages.agents.recommender import recommender
from packages.schemas import (
    MAX_SCORE_WITHOUT_EVIDENCE,
    AIMIPillar,
    AIMIScore,
    BriefingStatus,
    Claim,
    Classification,
    Complexity,
    Evidence,
    GraphState,
    PillarScore,
    Priority,
    Product,
    Recommendation,
    ROIEstimate,
    RunStatus,
    StartupProfile,
    Technology,
)

_FETCHED = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)


def _ev(url: str = "https://startup.example", snippet: str = "trecho público") -> Evidence:
    return Evidence(url=url, snippet=snippet, fetched_at=_FETCHED, content_hash="h1")


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


def _rec(
    tech: str,
    prioridade: Priority = Priority.ALTA,
    *,
    complexidade: Complexity = Complexity.MEDIA,
    proxima_acao: str = "Provisionar e medir.",
) -> Recommendation:
    return Recommendation(
        tech=tech,
        justificativa_tecnica="téc",
        justificativa_negocio="neg",
        prioridade=prioridade,
        complexidade=complexidade,
        proxima_acao=proxima_acao,
        evidencia_gap=[_ev()],
        evidencia_nvidia=[_ev(url="https://docs.nvidia.com/nim", snippet="NVIDIA NIM")],
    )


def _roi(*, is_live_run: bool = False) -> ROIEstimate:
    """ROI da célula `medium` ilustrativa (160/50 tok/s; p95 950 vs 2500; $0,18 vs $0,50)."""
    return ROIEstimate(
        throughput_speedup=3.2,
        latency_p95_delta_pct=-62.0,
        cost_delta_pct=-64.0,
        baseline="API externa (pay-per-token)",
        optimized="NIM (TensorRT-LLM + Triton)",
        benchmark_source="medium/7-8B — ilustrativo",
        is_live_run=is_live_run,
    )


def _rec_with_roi(roi: ROIEstimate, tech: str = "NVIDIA NIM") -> Recommendation:
    return _rec(tech).model_copy(update={"roi": roi})


def _healthcare_wrapper() -> StartupProfile:
    """AI-native de saúde dependente de API externa (2 hosts) → P3 baixo + setor saúde (§5.5)."""
    return StartupProfile(
        nome="MediChat",
        descricao=Claim[str](
            value=(
                "Assistente de IA para clínicas: usa a API da OpenAI para responder dúvidas "
                "de pacientes e apoiar diagnóstico em saúde."
            ),
            evidence=[_ev()],
        ),
        setor=Claim[str](value="Saúde / healthtech", evidence=[_ev()]),
        produtos=[Product(nome="Assistente", descricao="chat de saúde", evidence=[_ev()])],
        tecnologias=[
            Technology(nome="OpenAI API", categoria="LLM provider", uso="via api", evidence=[_ev()])
        ],
        source_urls=["https://medichat.example", "https://news.example"],
    )


# --- Espinha determinista ---------------------------------------------------------------------


def test_build_briefing_carries_diagnosis_recs_and_three_axes() -> None:
    aimi = _aimi(20, 20, 4, 22)  # gap severo em P3 (alvo de graduação)
    recs = [_rec("NVIDIA NIM")]
    b = build_briefing(aimi, None, recs, empresa="ACME", run_id="r1")

    assert b.status is BriefingStatus.NORMAL
    assert b.idioma == "pt-BR"
    assert b.empresa == "ACME"
    assert b.run_id == "r1"
    assert b.aimi is aimi  # diagnóstico carregado (não recalculado)
    assert b.recomendacoes == recs  # recomendações carregadas
    # os três eixos do §2 preenchidos
    assert b.acao_comercial and b.acao_tecnica and b.acao_comunitaria
    assert b.generated_at is None  # reprodutível (sem now(), igual aos terminais)


def test_resumo_grounds_on_class_total_and_main_gap() -> None:
    aimi = _aimi(20, 20, 4, 22)
    b = build_briefing(aimi, None, [_rec("NVIDIA NIM")], empresa="ACME")
    resumo = b.resumo_executivo
    assert "AI-native" in resumo  # a classe
    assert f"{aimi.total}/100" in resumo  # o AIMI total
    assert "Technical Optimization" in resumo  # o principal gap (P3, o mais severo)
    assert "NVIDIA NIM" in resumo  # a tech prescrita


def test_acao_comercial_prioritizes_graduation_target() -> None:
    # P3 é o gap + há recomendação ⇒ alvo de graduação API→stack (maior upside).
    b = build_briefing(_aimi(20, 20, 4, 22), None, [_rec("NVIDIA NIM")], empresa="ACME")
    assert "graduação" in b.acao_comercial.lower()


def test_acao_comercial_relationship_when_mature() -> None:
    # AIMI alto (≥60) sem gap de P3 ⇒ outreach de relacionamento (P4), não graduação.
    b = build_briefing(_aimi(20, 20, 18, 18), None, [_rec("NVIDIA NeMo")], empresa="ACME")
    assert "relacionamento" in b.acao_comercial.lower()
    assert "graduação" not in b.acao_comercial.lower()


def test_acao_tecnica_anchors_on_top_priority_recommendation() -> None:
    recs = [
        _rec("Triton", Priority.MEDIA, proxima_acao="Empacotar no Triton."),
        _rec("NVIDIA NIM", Priority.ALTA, proxima_acao="Provisionar o NIM e medir."),
    ]
    b = build_briefing(_aimi(20, 20, 4, 22), None, recs, empresa="ACME")
    # a recomendação de maior prioridade (alta) abre o eixo técnico, com sua próxima ação
    assert b.acao_tecnica.startswith("Começar por NVIDIA NIM")
    assert "Provisionar o NIM e medir." in b.acao_tecnica
    assert "NVIDIA NIM → Triton" in b.acao_tecnica  # roadmap por prioridade


def test_briefing_without_recommendations_is_honest() -> None:
    # Diagnóstico sem recomendação (sem evidência NVIDIA casada) → não inventa tech; texto honesto.
    b = build_briefing(_aimi(20, 20, 4, 22), None, [], empresa="ACME")
    assert b.recomendacoes == []
    assert "evidência suficiente" in b.acao_tecnica
    assert "evidência suficiente" in b.resumo_executivo


def test_build_briefing_is_deterministic() -> None:
    aimi = _aimi(20, 20, 4, 22)
    recs = [_rec("NVIDIA NIM")]
    assert build_briefing(aimi, None, recs, empresa="ACME") == build_briefing(
        aimi, None, recs, empresa="ACME"
    )


# --- Markdown (view PT-BR) --------------------------------------------------------------------


def test_render_markdown_covers_diagnosis_recs_and_axes() -> None:
    aimi = _aimi(20, 20, 4, 22)
    recs = [_rec("NVIDIA NIM", proxima_acao="Provisionar o NIM.")]
    md = render_markdown(build_briefing(aimi, None, recs, empresa="ACME"))

    assert md.startswith("# Briefing executivo — ACME")
    assert "## Resumo executivo" in md
    assert "## Diagnóstico (AIMI)" in md
    assert "AI-native" in md and f"{aimi.total}/100" in md
    assert "### NVIDIA NIM" in md
    assert "Provisionar o NIM." in md
    assert "https://docs.nvidia.com/nim" in md  # evidência NVIDIA citada
    assert "## Próximas ações" in md
    assert "**Comercial:**" in md and "**Técnica:**" in md and "**Comunidade (Inception):**" in md


def test_render_markdown_shows_roi_line_when_present() -> None:
    # F6.11 — com ROI anexado (matriz/benchmark), o texto do briefing crava os números (paridade
    # com o cartão RoiStrip da UI): throughput/custo/p95 + migração + proveniência honesta.
    aimi = _aimi(20, 20, 4, 22)
    md = render_markdown(build_briefing(aimi, None, [_rec_with_roi(_roi())], empresa="ACME"))
    assert "**ROI (graduação de inferência):**" in md
    assert "throughput 3.2x" in md
    assert "custo -64.0%" in md and "p95 -62.0%" in md  # sinal explícito; negativo = melhora
    assert "API externa (pay-per-token) → NIM (TensorRT-LLM + Triton)" in md
    assert "matriz de benchmark" in md and "medido ao vivo" not in md  # ilustrativa, não medida
    assert "fonte: medium/7-8B — ilustrativo" in md


def test_render_markdown_roi_marks_live_run() -> None:
    # is_live_run=True (medição real do NIM) → a proveniência muda de "matriz" p/ "medido ao vivo".
    recs = [_rec_with_roi(_roi(is_live_run=True))]
    md = render_markdown(build_briefing(_aimi(20, 20, 4, 22), None, recs, empresa="X"))
    assert "medido ao vivo" in md and "matriz de benchmark" not in md


def test_render_markdown_omits_roi_line_without_roi() -> None:
    # Sem ROI (sem matriz/benchmark) a recomendação degrada graciosa: nenhuma linha de ROI (F5.6).
    base = build_briefing(_aimi(20, 20, 4, 22), None, [_rec("NVIDIA NIM")], empresa="X")
    assert "ROI (graduação de inferência)" not in render_markdown(base)  # ausente sem rec.roi


def test_render_markdown_handles_terminal_briefing_with_lacunas() -> None:
    # A view também serve os terminais (F2.12): sem AIMI/recomendações, mostra as lacunas.
    from packages.schemas import Briefing

    terminal = Briefing(
        empresa="X",
        status=BriefingStatus.DADOS_INSUFICIENTES,
        resumo_executivo="dados insuficientes",
        lacunas=["corroboração insuficiente: 1 fonte"],
    )
    md = render_markdown(terminal)
    assert "## Diagnóstico (AIMI)" not in md  # sem AIMI → bloco omitido
    assert "## Lacunas" in md
    assert "1 fonte" in md


# --- PDF (view server-side, F4.6) -------------------------------------------------------------


def _pdf_text(pdf: bytes) -> str:
    """Texto extraído do PDF (via pypdf) — p/ asseverar o conteúdo da view sem fixar o layout."""
    from io import BytesIO

    from pypdf import PdfReader

    return "\n".join(page.extract_text() for page in PdfReader(BytesIO(pdf)).pages)


def test_render_pdf_is_valid_and_covers_diagnosis_recs_and_axes() -> None:
    aimi = _aimi(20, 20, 4, 22)
    recs = [_rec("NVIDIA NIM", proxima_acao="Provisionar o NIM.")]
    pdf = render_pdf(build_briefing(aimi, None, recs, empresa="ACME"))

    assert isinstance(pdf, bytes) and pdf.startswith(b"%PDF-")  # PDF válido
    text = _pdf_text(pdf)
    assert "Briefing executivo — ACME" in text
    assert "Resumo executivo" in text
    assert "Diagnóstico (AIMI)" in text
    assert "AI-native" in text and f"{aimi.total}/100" in text
    assert "Recomendações NVIDIA" in text and "NVIDIA NIM" in text
    assert "Provisionar o NIM." in text
    assert "https://docs.nvidia.com/nim" in text  # evidência NVIDIA citada (os dois lados)
    assert "Próximas ações" in text


def test_render_pdf_shows_roi_line_when_present() -> None:
    # A view PDF (F4.6) também crava o ROI numérico quando há matriz/benchmark anexado.
    aimi = _aimi(20, 20, 4, 22)
    pdf = render_pdf(build_briefing(aimi, None, [_rec_with_roi(_roi())], empresa="ACME"))
    text = _pdf_text(pdf)
    assert "ROI (graduação de inferência)" in text
    assert "3.2x" in text and "-64.0%" in text  # throughput + custo
    assert "matriz de benchmark" in text


def test_render_pdf_is_deterministic() -> None:
    # invariant=1 → data e ID do PDF fixos: mesmos bytes a cada chamada (run reprodutível, F4.4).
    aimi = _aimi(20, 20, 4, 22)
    recs = [_rec("NVIDIA NIM")]
    assert render_pdf(build_briefing(aimi, None, recs, empresa="ACME")) == render_pdf(
        build_briefing(aimi, None, recs, empresa="ACME")
    )


def test_render_pdf_handles_terminal_briefing_with_lacunas() -> None:
    # A view PDF também serve os terminais (F2.12): sem AIMI/recomendações, mostra as lacunas.
    from packages.schemas import Briefing

    terminal = Briefing(
        empresa="X",
        status=BriefingStatus.DADOS_INSUFICIENTES,
        resumo_executivo="dados insuficientes",
        lacunas=["corroboração insuficiente: 1 fonte"],
    )
    text = _pdf_text(render_pdf(terminal))
    assert "Diagnóstico (AIMI)" not in text  # sem AIMI → bloco omitido
    assert "Lacunas" in text and "1 fonte" in text


# --- Caminho LLM (refino plugável, fallback) --------------------------------------------------


def test_llm_refines_prose_but_preserves_diagnosis_and_recs() -> None:
    aimi = _aimi(20, 20, 4, 22)
    recs = [_rec("NVIDIA NIM")]
    base = build_briefing(aimi, None, recs, empresa="ACME")
    raw = json.dumps(
        {
            "resumo_executivo": "RESUMO REFINADO",
            "acao_comercial": "COMERCIAL REFINADA",
            "acao_tecnica": "TECNICA REFINADA",
            "acao_comunitaria": "COMUNITARIA REFINADA",
        }
    )
    refined = refine_with_llm(base, refine=lambda _b: raw)
    assert refined is not None
    assert refined.resumo_executivo == "RESUMO REFINADO"
    assert refined.acao_comercial == "COMERCIAL REFINADA"
    # diagnóstico e recomendações são os do estado — o LLM não toca na proveniência.
    assert refined.aimi is aimi
    assert refined.recomendacoes == recs
    assert refined.status is BriefingStatus.NORMAL


def test_llm_falls_back_to_none_on_bad_json() -> None:
    base = build_briefing(_aimi(20, 20, 4, 22), None, [_rec("NVIDIA NIM")], empresa="ACME")
    assert refine_with_llm(base, refine=lambda _b: "isto nao e json") is None


def test_make_briefing_default_is_deterministic_skeleton() -> None:
    aimi = _aimi(20, 20, 4, 22)
    recs = [_rec("NVIDIA NIM")]
    # sem adapter e com o flag off (default) → espinha determinista (== build_briefing).
    assert make_briefing(aimi, None, recs, empresa="ACME") == build_briefing(
        aimi, None, recs, empresa="ACME"
    )


def test_make_briefing_uses_injected_adapter() -> None:
    raw = json.dumps({"resumo_executivo": "REFINADO"})
    b = make_briefing(
        _aimi(20, 20, 4, 22), None, [_rec("NVIDIA NIM")], empresa="ACME", refine=lambda _b: raw
    )
    assert b.resumo_executivo == "REFINADO"


# --- O nó ------------------------------------------------------------------------------------


def test_node_is_noop_without_diagnosis() -> None:
    # Caminho normal sem aimi (espinha offline): fecha o run sem briefing (espinha verde M2).
    state = GraphState(run_id="x", query="q", status=RunStatus.RUNNING)
    assert briefing(state) == {"status": RunStatus.COMPLETED}


def test_node_emits_normal_briefing_with_diagnosis() -> None:
    aimi = _aimi(20, 20, 4, 22)
    state = GraphState(
        run_id="r", query="ACME", aimi=aimi, recommendations=[_rec("NVIDIA NIM")]
    )
    update = briefing(state)
    assert update["status"] is RunStatus.COMPLETED
    b = update["briefing"]
    assert b.status is BriefingStatus.NORMAL
    assert b.empresa == "ACME"  # cai na query sem perfil
    assert b.recomendacoes  # diagnóstico + recomendação carregados


def test_node_dispatches_terminal_status() -> None:
    profile = _healthcare_wrapper()
    insuf = GraphState(
        run_id="r", query="X", profile=profile, status=RunStatus.INSUFFICIENT_DATA
    )
    assert briefing(insuf)["briefing"].status is BriefingStatus.DADOS_INSUFICIENTES
    oos = GraphState(
        run_id="r",
        query="X",
        profile=profile,
        aimi=heuristic_score(profile),
        status=RunStatus.OUT_OF_SCOPE,
    )
    assert briefing(oos)["briefing"].status is BriefingStatus.FORA_DE_ESCOPO


def test_node_end_to_end_over_real_rag() -> None:
    profile = _healthcare_wrapper()
    aimi = heuristic_score(profile)
    rag = nvidia_rag(GraphState(run_id="r", query="x", profile=profile, aimi=aimi))
    rec_update = recommender(
        GraphState(run_id="r", query="x", profile=profile, aimi=aimi, retrieved=rag["retrieved"])
    )
    state = GraphState(
        run_id="r",
        query="x",
        profile=profile,
        aimi=aimi,
        retrieved=rag["retrieved"],
        recommendations=rec_update["recommendations"],
    )
    update = briefing(state)
    b = update["briefing"]
    assert b.status is BriefingStatus.NORMAL
    assert b.empresa == "MediChat"
    assert b.recomendacoes  # saúde + wrapper de API ⇒ ao menos uma recomendação
    assert b.acao_comercial and b.acao_tecnica and b.acao_comunitaria
    # o Markdown renderiza a recomendação real e sua evidência NVIDIA
    md = render_markdown(b)
    assert b.recomendacoes[0].tech in md


def test_graph_routes_to_normal_briefing() -> None:
    # Ponta a ponta no grafo: perfil AI-native corroborado (2 hosts) flui search→...→briefing
    # normal, com diagnóstico + recomendação e os três eixos — sem terminal.
    init = GraphState(run_id="run-normal", query="MediChat", profile=_healthcare_wrapper())
    out = GraphState.model_validate(compile_graph().invoke(init, {}))

    assert out.status is RunStatus.COMPLETED
    assert out.briefing is not None
    assert out.briefing.status is BriefingStatus.NORMAL
    assert out.briefing.recomendacoes  # recomendação NVIDIA com evidência dos dois lados
    assert out.briefing.acao_tecnica
    assert out.errors == []
