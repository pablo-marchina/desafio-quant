import sys
from types import SimpleNamespace

from agents.nvidia import recommendation_agent as agent


def test_no_gap_recommends_by_functional_fit(monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "rag.generation.rag_query",
        SimpleNamespace(build_context=lambda _: "[Fonte 1] NVIDIA service"),
    )
    monkeypatch.setattr(
        agent,
        "call_json",
        lambda *_: {
            "recomendacoes_nvidia": [
                {
                    "produto": "NVIDIA NIM",
                    "justificativa": "Aderente à inferência preditiva.",
                    "fontes": ["[Fonte 1]"],
                }
            ],
            "tradeoffs": [],
            "pontos_a_validar": [],
            "status": "ok",
        },
    )
    result = agent.recommendation_agent(
        {
            "startup_mencionada": True,
            "empresa": "Axenya",
            "servico_startup_analisado": (
                "Plataforma de saúde com modelos preditivos."
            ),
            "gaps_identificados": [],
            "rag_answer": "NVIDIA service",
            "retrieved_chunks": [{"text": "NVIDIA service"}],
            "question": "Recomende um serviço NVIDIA para Axenya",
            "output_mode": "recommendation",
        }
    )
    recommendation = result["recomendacoes_nvidia"][0]
    assert recommendation["produto"] == "NVIDIA NIM"
    assert recommendation["base_recomendacao"] == "aderencia_funcional"
    assert "nenhum gap documentado" in recommendation["gap"]


def test_recommendation_converts_source_citations_to_urls(monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "rag.generation.rag_query",
        SimpleNamespace(build_context=lambda _: "[Fonte 1] NVIDIA service"),
    )
    monkeypatch.setattr(
        agent,
        "call_json",
        lambda *_: {
            "recomendacoes_nvidia": [
                {
                    "produto": "NVIDIA NIM",
                    "justificativa": "Aderente Ã  inferÃªncia.",
                    "fontes": ["[Fonte 1]"],
                }
            ],
            "tradeoffs": [],
            "pontos_a_validar": [],
            "roadmap": ["Validar latÃªncia."],
            "comparacao_bigtechs": ["Comparar com endpoint gerenciado."],
            "status": "ok",
        },
    )
    result = agent.recommendation_agent(
        {
            "startup_mencionada": True,
            "empresa": "Axenya",
            "servico_startup_analisado": "Plataforma preditiva.",
            "gaps_identificados": [],
            "rag_answer": "NVIDIA service",
            "retrieved_chunks": [
                {
                    "text": "NVIDIA service",
                    "source_url": "https://docs.nvidia.com/nim",
                }
            ],
            "question": "Recomende um serviÃ§o NVIDIA para Axenya",
            "output_mode": "recommendation",
        }
    )

    recommendation = result["recomendacoes_nvidia"][0]
    assert recommendation["fontes"] == ["https://docs.nvidia.com/nim"]
    assert result["structured_output"]["roadmap"] == ["Validar latÃªncia."]


def test_no_gap_and_no_service_keeps_insufficient_data(monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "rag.generation.rag_query",
        SimpleNamespace(build_context=lambda _: ""),
    )
    result = agent.recommendation_agent(
        {
            "startup_mencionada": True,
            "empresa": "Sem contexto",
            "gaps_identificados": [],
            "retrieved_chunks": [],
            "question": "Recomende",
            "output_mode": "recommendation",
        }
    )
    assert result["recomendacoes_nvidia"] == []
