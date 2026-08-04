from app.services.ai_evidence_pipeline import executar_pipeline_investigacao_ia
from tests.test_scraper_agent import FakeSession


def test_ai_evidence_pipeline_runs_planner_and_scraper_together(tmp_path, monkeypatch):
    monkeypatch.setenv("SEARCH_PROVIDER", "searxng")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "firecrawl-test")
    startup = {
        "nome": "Clara Pagamentos",
        "site": "https://clara.com.br",
        "categoria": "Financeiro",
        "descricao_curta": "Plataforma de gestão de gastos corporativos com automação.",
    }

    resultado = executar_pipeline_investigacao_ia(
        startup,
        session=FakeSession(),
        delay_seconds=0,
        respect_robots=False,
        salvar_resultado=True,
        output_dir=tmp_path,
        validation_output_dir=tmp_path,
        classification_output_dir=tmp_path,
    )

    assert resultado["startup"] == "Clara Pagamentos"
    assert resultado["status"] == "completo"
    assert resultado["plano"]["tarefas"]
    assert len(resultado["plano"]["tarefas"]) == len(resultado["plano"]["plano_consultas"]) + 1
    assert resultado["coleta"]["metricas"]["tarefas_executadas"] == len(resultado["plano"]["tarefas"])
    assert "resumo_consolidado" in resultado["validacao"]
    assert resultado["classificacao_ia"]["classificacao"] in {
        "AI-native",
        "AI-enabled",
        "API-consumer",
        "Non-AI",
    }
    assert resultado["arquivo_saida"] is not None
    assert resultado["arquivo_validacao"] is not None
    assert resultado["arquivo_classificacao"] is not None
