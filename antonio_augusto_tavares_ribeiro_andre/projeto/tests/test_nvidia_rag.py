"""Testes do nó nvidia_rag (F3.7) — RAG híbrido guiado pelos gaps → evidência citável.

Tudo offline/determinista (sobre a espinha verde da F3.5/F3.6: HashingEmbedder + índice
in-memory + LexicalReranker). Exercita:

1. **Query derivada dos gaps** (`build_rag_queries`): uma busca por gap (menor score primeiro,
   Technical Optimization incluso), a de setor (§5.5) anexada, e o fallback ao pilar mais baixo
   quando não há gap explícito.
2. **O nó** (`nvidia_rag`): popula `state.retrieved` com ≥ 2 citações da KB, com proveniência
   citável (§8) e rastreabilidade gap→evidência (F4.1); filtra o grounding da rubrica (F3.1d);
   carimba o trace; é determinístico; e é no-op limpo sem `aimi` (espinha verde, M2).
3. **Recuperação por setor** (§5.5): perfil de saúde traz MONAI/Clara na evidência.
"""

from __future__ import annotations

from datetime import UTC, datetime

from packages.agents import build_rag_queries, retrieve_evidence
from packages.agents.classifier import heuristic_score
from packages.agents.nvidia_rag import (
    MAX_CITATIONS,
    PILLAR_QUERIES,
    get_kb_retriever,
    nvidia_rag,
)
from packages.rag import LexicalReranker, build_retriever
from packages.schemas import (
    MAX_SCORE_WITHOUT_EVIDENCE,
    AIMIPillar,
    AIMIScore,
    Claim,
    Classification,
    Evidence,
    GraphState,
    PillarScore,
    Product,
    StartupProfile,
    Technology,
)

_FETCHED = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)


def _ev(
    url: str = "https://startup.example", snippet: str = "trecho público de suporte"
) -> Evidence:
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


# --- Query derivada dos gaps ----------------------------------------------------------------


def test_queries_follow_gap_severity_and_include_technical_optimization() -> None:
    # P3 (4) e P2 (10) são gaps (≤12); P1/P4 estão estabelecidos. Ordem = menor score primeiro.
    queries = build_rag_queries(_aimi(20, 10, 4, 22), profile=None)
    assert [q.pilar for q in queries] == [
        AIMIPillar.TECHNICAL_OPTIMIZATION,
        AIMIPillar.WORKFLOW_DEPTH,
    ]
    # cada gap mapeia para a busca da tech NVIDIA que o fecha (uma por gap, não genérica).
    assert queries[0].text == PILLAR_QUERIES[AIMIPillar.TECHNICAL_OPTIMIZATION]


def test_sector_query_is_appended_for_healthcare() -> None:
    queries = build_rag_queries(_aimi(4, 4, 4, 4), profile=_healthcare_wrapper())
    sector = [q for q in queries if q.pilar is None]
    assert len(sector) == 1
    assert "monai" in sector[0].text.lower()  # §5.5: saúde → MONAI/Clara


def test_without_explicit_gap_uses_lowest_pillar() -> None:
    # Startup madura (nenhum pilar ≤12): ainda há uma busca, guiada pelo pilar mais baixo.
    queries = build_rag_queries(_aimi(20, 22, 18, 24), profile=None)
    assert len(queries) == 1
    assert queries[0].pilar is AIMIPillar.TECHNICAL_OPTIMIZATION


def test_technical_optimization_gap_leads_and_survives_max_gaps() -> None:
    # Acoplamento F6.3: P3 baixo é o gatilho de graduação, mesmo NÃO sendo o gap mais severo.
    # Aqui P1/P2/P4 (2/3/5) estão abaixo de P3 (12) — pela severidade pura P3 cairia fora do
    # corte MAX_GAPS=3 e a recomendação de graduação NÃO dispararia. A priorização da F6.3 põe
    # P3 à frente e garante que ele sobreviva ao corte.
    queries = build_rag_queries(_aimi(2, 3, 12, 5), profile=None)
    assert queries[0].pilar is AIMIPillar.TECHNICAL_OPTIMIZATION  # P3 encabeça
    assert queries[0].text == PILLAR_QUERIES[AIMIPillar.TECHNICAL_OPTIMIZATION]
    # P3 está entre os MAX_GAPS selecionados (não foi cortado pelos pilares mais baixos).
    assert AIMIPillar.TECHNICAL_OPTIMIZATION in {q.pilar for q in queries}


# --- O nó: evidência citável guiada pelos gaps ----------------------------------------------


def test_node_populates_cited_evidence_from_gaps() -> None:
    profile = _healthcare_wrapper()
    state = GraphState(
        run_id="run-rag", query="MediChat", profile=profile, aimi=heuristic_score(profile)
    )
    update = nvidia_rag(state)
    retrieved = update["retrieved"]
    assert len(retrieved) >= 2  # DoD F3: resposta com ≥2 citações
    for chunk in retrieved:
        # proveniência citável (§8) + rastreabilidade gap→evidência (F4.1).
        assert chunk.text
        assert chunk.source_url is not None
        assert chunk.metadata["tech"]
        assert chunk.metadata["chunk_id"]
        assert chunk.metadata["gap"]  # qual gap/setor recuperou o trecho
        assert chunk.metadata["source_type"] != "grounding"  # rubrica AIMI fica de fora (F3.1d)
    # ordenado por relevância (rerank) desc — a ordem que o recommender (F4) consome.
    scores = [c.score for c in retrieved]
    assert scores == sorted(scores, reverse=True)
    assert len(retrieved) <= MAX_CITATIONS
    # trace observável (§8): as consultas e o reranker usado ficam registrados.
    assert update["trace"]["rag"]["n_citations"] == len(retrieved)
    assert update["trace"]["rag"]["queries"]


def test_node_is_noop_without_diagnosis() -> None:
    # Espinha offline sem classificação (aimi None): nada a recuperar → no-op limpo (M2/DoD).
    state = GraphState(run_id="run-empty", query="qualquer")
    assert nvidia_rag(state) == {}


def test_node_is_deterministic() -> None:
    profile = _healthcare_wrapper()
    aimi = heuristic_score(profile)
    first = nvidia_rag(GraphState(run_id="a", query="x", profile=profile, aimi=aimi))["retrieved"]
    second = nvidia_rag(GraphState(run_id="b", query="x", profile=profile, aimi=aimi))["retrieved"]
    assert [c.metadata["chunk_id"] for c in first] == [c.metadata["chunk_id"] for c in second]
    assert [c.score for c in first] == [c.score for c in second]


def test_injected_retriever_and_reranker_are_used() -> None:
    profile = _healthcare_wrapper()
    state = GraphState(run_id="inj", query="x", profile=profile, aimi=heuristic_score(profile))
    update = nvidia_rag(state, retriever=build_retriever(), reranker=LexicalReranker())
    assert update["retrieved"]
    assert update["trace"]["rag"]["reranker"] == "lexical-offline"


# --- Recuperação por setor (§5.5) -----------------------------------------------------------


def test_sector_retrieval_surfaces_domain_tech_for_healthcare() -> None:
    profile = _healthcare_wrapper()
    queries = build_rag_queries(heuristic_score(profile), profile)
    citations = retrieve_evidence(
        queries, retriever=get_kb_retriever(), reranker=LexicalReranker()
    )
    # a busca de setor (saúde) traz MONAI/Clara para a evidência recuperável (§5.5).
    haystack = " ".join((c.text + " " + (c.source_title or "")).lower() for c in citations)
    assert "monai" in haystack or "clara" in haystack


def test_retrieve_evidence_dedups_chunks_across_gaps() -> None:
    profile = _healthcare_wrapper()
    queries = build_rag_queries(heuristic_score(profile), profile)
    citations = retrieve_evidence(
        queries, retriever=get_kb_retriever(), reranker=LexicalReranker()
    )
    ids = [c.metadata["chunk_id"] for c in citations]
    assert len(ids) == len(set(ids))  # um trecho aparece uma vez, mesmo servindo a vários gaps
