from app.core.schemas import NVIDIARecommendationOutput
from app.services.enterprise_pipeline import (
    STAGE_CACHE_VERSIONS,
    EnterprisePipeline,
    run_enterprise_pipeline,
)
from tests.test_scraper_agent import FakeSession


class FakeRecommender:
    def recommend(self, maturity):
        return NVIDIARecommendationOutput(
            startup=maturity.startup,
            recomendacoes=[],
            chunks_utilizados=[],
            aviso="Base de teste sem recomendações.",
        )


def test_enterprise_pipeline_returns_all_nine_trace_stages(monkeypatch, tmp_path):
    monkeypatch.setenv("SEARCH_PROVIDER", "searxng")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "firecrawl-test")

    result = run_enterprise_pipeline(
        {
            "startup_name": "Clara Pagamentos",
            "site_oficial": "https://clara.com.br",
            "categoria": "Financeiro",
            "descricao_curta": "Plataforma financeira com automacao.",
        },
        session=FakeSession(),
        recommender=FakeRecommender(),
        cache=None,
        use_cache=False,
        delay_seconds=0,
        retry_wait_multiplier=0,
    )

    assert result["status"] in {"completo", "parcial"}
    assert set(result["trace"]) == {
        "search_planner",
        "scraper",
        "evidence_validator",
        "ai_maturity_classifier",
        "inception_fit",
        "nvidia_recommender_rag",
        "recommendation_refiner",
        "impact_estimator",
        "briefing_generator",
    }
    assert result["classificacao"] in {"AI-native", "AI-enabled", "API-consumer", "Non-AI"}
    assert result["recomendacao"]["startup"] == "Clara Pagamentos"
    assert result["inception_fit"]["eligibility_status"] == "unknown"
    assert result["recomendacao_refinada"]["startup"] == "Clara Pagamentos"
    assert result["impacto_estimado"]["startup"] == "Clara Pagamentos"
    assert result["briefing_markdown"].startswith("# Briefing NVIDIA Inception")
    assert all("output" in stage for stage in result["trace"].values())


def test_rag_cache_version_is_bumped_when_retrieval_contract_changes():
    assert STAGE_CACHE_VERSIONS["nvidia_recommender_rag"] == "v2"


def test_enterprise_pipeline_is_compiled_as_state_graph(monkeypatch, tmp_path):
    monkeypatch.setenv("LANGGRAPH_CHECKPOINT_PATH", str(tmp_path / "checkpoints.sqlite"))
    pipeline = EnterprisePipeline(
        session=FakeSession(),
        recommender=FakeRecommender(),
        use_cache=False,
        delay_seconds=0,
        retry_wait_multiplier=0,
    )

    graph = pipeline.runnable.get_graph()
    assert "research_feedback" in graph.nodes
    assert "evidence_validator" in graph.nodes
    assert "briefing_generator" in graph.nodes
    assert pipeline.checkpointer is not None


def test_source_warning_does_not_become_critical_when_results_exist():
    pipeline = object.__new__(EnterprisePipeline)
    state = {
        "warnings": [],
        "source_errors": [],
        "critical_errors": [],
        "errors": [],
    }
    output = {
        "status": "parcial",
        "resultados_buscas": [
            {"titulo": "Fonte", "url": "https://example.com", "snippet": "IA"}
        ],
        "paginas_completas": [],
        "erros": [{"erro": "Uma fonte retornou 403"}],
    }

    warnings, critical = pipeline._record_output_diagnostics(state, "scraper", output)

    assert warnings == ["scraper: Uma fonte retornou 403"]
    assert state["source_errors"] == warnings
    assert state["critical_errors"] == []
    assert critical is None


def test_missing_all_sources_is_a_critical_error():
    pipeline = object.__new__(EnterprisePipeline)
    state = {
        "warnings": [],
        "source_errors": [],
        "critical_errors": [],
        "errors": [],
    }

    _, critical = pipeline._record_output_diagnostics(
        state,
        "scraper",
        {"status": "parcial", "resultados_buscas": [], "paginas_completas": [], "erros": []},
    )

    assert critical == "scraper: nenhuma fonte utilizavel foi coletada"
    assert state["critical_errors"] == [critical]


def test_pipeline_notifies_active_stage_before_execution():
    events = []

    class Hook:
        def stage_started(self, state, stage):
            events.append(("started", stage))

        def stage_completed(self, state, stage, output):
            events.append(("completed", stage))

    class Cache:
        def key_for(self, namespace, payload):
            return "unused"

    pipeline = object.__new__(EnterprisePipeline)
    pipeline.cache = Cache()
    pipeline.use_cache = False
    pipeline.retry_wait_multiplier = 0
    pipeline.persistence_hook = Hook()
    state = {
        "input": {"startup_name": "Teste"},
        "trace": {},
        "errors": [],
        "warnings": [],
        "source_errors": [],
        "critical_errors": [],
    }

    pipeline._execute_stage(
        state,
        stage="scraper",
        input_payload={},
        output_key="scraper_output",
        operation=lambda: {
            "status": "completo",
            "resultados_buscas": [{"url": "https://example.com"}],
        },
    )

    assert events == [("started", "scraper"), ("completed", "scraper")]
