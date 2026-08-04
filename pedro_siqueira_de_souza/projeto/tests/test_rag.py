"""Testes do NVIDIA RAG Agent — offline.

Troca `agents.rag.retrieve_and_rerank` por um fake determinístico (mesma costura
do get_llm/fetch_static): nada de Qdrant, OpenAI ou Cohere. Testa-se a MECÂNICA
do nó — montar a query do perfil, pular perfis pobres, isolar erro por startup e
preencher `rag_contexts`.
"""
import pytest

from agents.rag import _build_query, rag_node
from rag.rerank import RerankedChunk


def _validated(name, **startup_fields):
    """Monta um item de `validated_startups` com o perfil dado."""
    startup = {
        "name": name,
        "description": None, "sector": None, "stage": None, "funding": None,
        "tech_stack": [], "ai_signals": [], "extraction_basis": "content",
    }
    startup.update(startup_fields)
    return {
        "classified": {
            "startup": startup,
            "label": "AI-native", "rationale": "x", "confidence": "high",
        },
        "validation_confidence": "high",
        "issues": [],
    }


FAKE_CHUNK = RerankedChunk(
    tech="NVIDIA NIM", url="https://x/nim", text="microsserviços de inferência",
    chunk_index=0, vector_score=0.4, rerank_score=0.9,
)


@pytest.fixture
def patch_rag(monkeypatch):
    """retrieve_and_rerank devolve sempre o mesmo chunk, registrando as queries."""
    chamadas = []

    def fake(query, top_n=4, **kwargs):
        chamadas.append(query)
        return [FAKE_CHUNK]

    monkeypatch.setattr("agents.rag.retrieve_and_rerank", fake)
    return chamadas


# --- _build_query ---------------------------------------------------------

def test_build_query_junta_os_campos_do_perfil():
    q = _build_query({
        "description": "plataforma de visão computacional",
        "sector": "agtech", "ai_signals": ["modelos próprios de CV"],
        "tech_stack": ["PyTorch"],
    })
    assert "visão computacional" in q
    assert "agtech" in q
    assert "modelos próprios de CV" in q
    assert "PyTorch" in q


def test_build_query_perfil_so_metadata_retorna_none():
    # só nome, nenhum campo descritivo -> não vale consultar
    assert _build_query({"name": "Acme"}) is None


# --- rag_node -------------------------------------------------------------

def test_rag_node_recupera_contexto_para_startup_com_perfil(patch_rag):
    state = {"validated_startups": [
        _validated("Aegro", description="gestão agrícola com IA", sector="agtech"),
    ]}
    out = rag_node(state)

    ctx = out["rag_contexts"][0]
    assert ctx["name"] == "Aegro"
    assert ctx["query"] is not None
    assert len(ctx["chunks"]) == 1
    assert ctx["chunks"][0]["tech"] == "NVIDIA NIM"
    assert "1/1" in out["messages"][0][1]


def test_rag_node_pula_perfil_pobre_sem_chamar_rag(patch_rag):
    state = {"validated_startups": [_validated("SemPerfil")]}  # só metadata
    out = rag_node(state)

    ctx = out["rag_contexts"][0]
    assert ctx["query"] is None
    assert ctx["chunks"] == []
    assert ctx["note"] == "perfil insuficiente para RAG"
    assert patch_rag == []  # retrieve_and_rerank NÃO foi chamado


def test_rag_node_isola_erro_por_startup(monkeypatch):
    def explode(query, top_n=4, **kwargs):
        raise RuntimeError("Qdrant fora do ar")

    monkeypatch.setattr("agents.rag.retrieve_and_rerank", explode)
    state = {"validated_startups": [
        _validated("Quebra", description="usa IA", sector="fintech"),
    ]}
    out = rag_node(state)

    ctx = out["rag_contexts"][0]
    assert ctx["chunks"] == []
    assert ctx["note"] == "falha ao consultar a base NVIDIA"


def test_rag_node_sem_startups_nao_quebra(patch_rag):
    out = rag_node({"validated_startups": []})
    assert out["rag_contexts"] == []


def test_grafo_compila_com_o_no_rag():
    # o grafo precisa compilar com o novo nó e a aresta rag -> END
    from agents.graph import build_graph

    grafo = build_graph()
    assert "rag" in grafo.get_graph().nodes
