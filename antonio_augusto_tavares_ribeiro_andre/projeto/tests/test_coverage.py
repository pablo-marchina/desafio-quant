"""Cobertura de recuperação da KB NVIDIA — teste de recuperação por tech (F3.8).

A F3.1 já garante (em `test_ingest.py`) que toda tech do §5.4 + MONAI está **no manifesto**.
Esta suíte fecha o outro lado do marco M3: que cada uma é de fato **recuperável pelo pipeline
real** (F3.1→F3.5, offline/determinístico) — não basta estar indexada, a busca híbrida tem de
trazê-la. Em especial cobre **NeMo Evaluator/avaliação**: o §5.5 recomenda governança como
*Guardrails + NeMo* (§5.5 do case), então uma consulta de avaliação/
governança precisa recuperar o Evaluator, **não só o Guardrails**.

Tudo roda sobre a espinha verde (HashingEmbedder + BM25 in-memory): sem rede/GPU e reprodutível.
"""

from __future__ import annotations

import pytest

from packages.rag import HybridRetriever, build_retriever, load_kb_sources

# Janela de candidatos em que a tech precisa aparecer para ser considerada "recuperável". É o
# default do retrieve (F3.5) e a janela que alimenta o rerank (F3.6) no nó nvidia_rag (F3.7);
# com as queries abaixo o pior caso fica em rank 2, então há folga real (não é top-1 frágil).
COVERAGE_LIMIT = 5

# Uma consulta representativa por tech recomendável do §5.4 (§10.2) + MONAI (F3.1c). As chaves
# DEVEM coincidir com as techs `source_type: doc` do manifesto — o teste de completude abaixo
# trava isso, então adicionar uma tech doc sem query de recuperação quebra o build (F3.8).
TECH_QUERIES = {
    "NVIDIA Inception": "programa NVIDIA Inception de aceleração para startups",
    "NVIDIA NIM": "microsserviços de inferência NIM para servir modelos em produção",
    "NVIDIA API Catalog": "catálogo de APIs e modelos hospedados em build.nvidia.com",
    "NVIDIA NeMo": "plataforma NeMo para customizar e treinar modelos generativos",
    "NeMo Guardrails": "NeMo Guardrails rails de tópico, segurança e anti-jailbreak em apps de LLM",
    "NVIDIA Triton Inference Server": "Triton Inference Server para servir modelos em produção",
    "TensorRT-LLM": "TensorRT-LLM otimização e compilação de inferência de LLM",
    "NVIDIA RAPIDS": "RAPIDS acelera o pipeline de pandas e scikit-learn na GPU",
    "cuDF": "cuDF dataframes acelerados por GPU compatível com pandas",
    "cuML": "cuML machine learning e clustering acelerado por GPU",
    "CUDA Toolkit": "CUDA Toolkit base de computação paralela em GPU",
    "NVIDIA Riva": "Riva reconhecimento de fala ASR e síntese de voz TTS",
    "NVIDIA Omniverse": "Omniverse simulação e gêmeos digitais 3D",
    "NVIDIA Isaac": "Isaac plataforma de robótica e IA física",
    "NVIDIA Clara": "Clara IA para saúde e imagem médica",
    "NVIDIA Morpheus": "Morpheus IA para cibersegurança",
    "NVIDIA AI Enterprise": "AI Enterprise plataforma de software de IA para produção",
    "MONAI": "MONAI deep learning para imagem médica em saúde",
}


def _recommendable_doc_techs() -> set[str]:
    """Techs recomendáveis do manifesto = fontes `source_type: doc` (§10.2 + MONAI).

    Exclui `grounding` (materiais AI-native do §10.1, que fundamentam o AIMI, F3.1d) e
    `video_transcript` (a tech guarda-chuva dos vídeos do §10.1, F3.1b) — nenhum dos dois é
    uma tech NVIDIA recomendável do §5.4.
    """
    return {s.tech for s in load_kb_sources() if s.source_type == "doc"}


@pytest.fixture(scope="module")
def retriever() -> HybridRetriever:
    """Retriever híbrido sobre a KB real (offline/determinístico), uma vez por módulo."""
    return build_retriever()


def test_query_map_covers_every_recommendable_doc_tech() -> None:
    # Completude: o mapa de recuperação cobre exatamente as techs recomendáveis do manifesto.
    # Se uma tech `doc` entrar sem query aqui (ou vice-versa), o build quebra — a cobertura não
    # silencia (mesma disciplina do CORE_TECHS em test_ingest.py, agora no nível de recuperação).
    assert set(TECH_QUERIES) == _recommendable_doc_techs()


@pytest.mark.parametrize("tech,query", sorted(TECH_QUERIES.items()))
def test_every_recommendable_tech_is_retrievable(
    retriever: HybridRetriever, tech: str, query: str
) -> None:
    # Teste de recuperação por tech (F3.8): cada tech do §5.4 + MONAI volta na janela de
    # candidatos do pipeline real — indexada E recuperável, com proveniência citável (§8).
    results = retriever.search(query, limit=COVERAGE_LIMIT)
    techs = [r.tech for r in results]
    assert tech in techs, f"{tech!r} não recuperável p/ {query!r}; veio {techs}"
    hit = next(r for r in results if r.tech == tech)
    assert hit.url.startswith("http") and hit.text  # recuperação citável, não só presente


def test_evaluation_governance_retrieves_nemo_evaluator(retriever: HybridRetriever) -> None:
    # §5.5: governança = Guardrails + NeMo (avaliação). Uma consulta de avaliação/governança
    # precisa recuperar o NeMo Evaluator — não só o Guardrails (F3.8). O Evaluator tem chunk
    # próprio na KB (seção dedicada em data/knowledge_base/docs/nvidia-nemo.md).
    results = retriever.search(
        "avaliação sistemática de qualidade dos modelos e do RAG, governança de IA", limit=5
    )
    def has_evaluator(r: object) -> bool:
        heading = (r.payload.get("heading") or "").lower()
        return "evaluator" in heading or "nemo evaluator" in r.text.lower()

    headings = [r.payload.get("heading") for r in results]
    assert any(has_evaluator(r) for r in results), f"NeMo Evaluator ausente; veio {headings}"


def test_grounding_material_is_not_a_recommendable_tech() -> None:
    # O grounding do §10.1 (Sequoia/Emergence/5-layer cake, F3.1d) fundamenta o AIMI, mas NÃO é
    # tech recomendável do §5.4 — fica fora das techs `doc` e do mapa de recuperação por tech.
    assert "AI-Native (grounding)" not in _recommendable_doc_techs()
    assert "AI-Native (grounding)" not in TECH_QUERIES
