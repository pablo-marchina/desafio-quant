from app.core.schemas import NVIDIARecommendationOutput
from app.persistence.persistence_service import PersistenceError
from app.persistence.pipeline_with_persistence import PipelinePersistenceHook
from app.services.enterprise_pipeline import run_enterprise_pipeline
from tests.test_scraper_agent import FakeSession


class FailingPersistence:
    def save_startup(self, data):
        raise PersistenceError("Supabase indisponível")


class FakeRecommender:
    def recommend(self, maturity):
        return NVIDIARecommendationOutput(
            startup=maturity.startup,
            recomendacoes=[],
            chunks_utilizados=[],
            aviso="Teste sem recomendações.",
        )


def test_pipeline_continues_when_persistence_is_unavailable(monkeypatch):
    monkeypatch.setenv("SEARCH_PROVIDER", "searxng")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "firecrawl-test")
    hook = PipelinePersistenceHook(FailingPersistence())

    result = run_enterprise_pipeline(
        {
            "startup_name": "Clara Pagamentos",
            "site_oficial": "https://clara.com.br",
            "categoria": "Financeiro",
        },
        session=FakeSession(),
        recommender=FakeRecommender(),
        persistence_hook=hook,
        use_cache=False,
        delay_seconds=0,
        retry_wait_multiplier=0,
    )

    assert result["status"] == "parcial"
    assert result["classificacao"] is not None
    assert result["recomendacao"] is not None
    assert any("persistence:initialization" in error for error in result["errors"])
