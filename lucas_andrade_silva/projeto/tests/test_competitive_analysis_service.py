from agents.nvidia import graph as graph_module
from scraper.api.services.competitive_analysis_service import (
    CompetitiveAnalysisService,
)


def test_competitive_service_builds_delivery_context(monkeypatch):
    captured = {}
    saved = {}

    class FakeStartupService:
        def update_startup(self, startup_id, data):
            saved["startup_id"] = startup_id
            saved["data"] = data
            return {"id": startup_id, **data}

    def fake_run_competitive_analysis(context, question):
        captured["context"] = context
        captured["question"] = question
        return {
            "final_answer": "comparacao pronta",
            "structured_output": {"schema_version": "competitive-analysis/v1"},
        }

    monkeypatch.setattr(
        graph_module, "run_competitive_analysis", fake_run_competitive_analysis
    )
    result = CompetitiveAnalysisService(FakeStartupService()).analyze(
        {
            "id": "1",
            "company_name": "Axenya",
            "validated_url": "https://axenya.com",
            "description": "Plataforma de saude com modelos preditivos.",
            "cnae": "6201-5/01 - Desenvolvimento de programas de computador",
            "tech_stack": ["Python"],
            "nvidia_recommendation": {
                "gaps": [{"gap": "latencia"}],
                "recommendations": [{"produto": "NVIDIA NIM"}],
            },
        },
        lambda _: None,
    )

    assert captured["question"] == "comparar com big techs"
    assert captured["context"]["empresa"] == "Axenya"
    assert captured["context"]["startup_url"] == "https://axenya.com"
    assert captured["context"]["cnae"] == "6201-5/01 - Desenvolvimento de programas de computador"
    assert captured["context"]["servico_startup_analisado"].startswith("Plataforma")
    assert captured["context"]["recomendacoes_nvidia"][0]["produto"] == "NVIDIA NIM"
    assert result["structured_output"]["schema_version"] == "competitive-analysis/v1"
    assert result["generated_at"]
    assert saved["startup_id"] == "1"
    assert saved["data"]["competitive_analysis"]["company_name"] == "Axenya"
