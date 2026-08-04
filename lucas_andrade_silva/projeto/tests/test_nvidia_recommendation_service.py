from agents.nvidia import graph as graph_module
from scraper.api.services.nvidia_recommendation_service import (
    NvidiaRecommendationService,
)


def test_service_passes_user_need_as_documented_gap(monkeypatch):
    captured = {}

    def fake_run_graph(question, **kwargs):
        captured["question"] = question
        captured.update(kwargs)
        return {
            "recomendacoes_nvidia": [
                {
                    "gap": "reduzir latência",
                    "produto": "NVIDIA NIM",
                }
            ],
            "gaps_identificados": [],
            "sources": [],
        }

    monkeypatch.setattr(graph_module, "run_graph", fake_run_graph)
    result = NvidiaRecommendationService().recommend(
        {"id": "1", "company_name": "Axenya"},
        lambda _: None,
        need=" reduzir   latência ",
    )

    assert captured["competitive_context"]["user_documented_need"] == (
        "reduzir latência"
    )
    assert captured["competitive_context"]["startup_context_preloaded"] is True
    assert captured["competitive_context"]["empresa"] == "Axenya"
    assert "Axenya precisa reduzir latência" in captured["question"]
    assert result["recommendations"][0]["produto"] == "NVIDIA NIM"
