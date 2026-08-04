from uuid import uuid4

from app.scraping.cubo_portfolio_scraper import StartupCubo
from app.services.startup_discovery_service import StartupDiscoveryService


class FakePersistence:
    def __init__(self) -> None:
        self.saved: list[dict] = []

    def save_startup_with_status(self, payload):
        self.saved.append(payload)
        return uuid4(), payload["nome"] != "Existente"


class FakeBatchRepository:
    def __init__(self) -> None:
        self.batch_id = uuid4()
        self.startups: list[dict] = []

    def create_batch(self, source_path, startups, options):
        self.startups = startups
        return self.batch_id


def _startup(nome: str, site: str) -> StartupCubo:
    return StartupCubo(
        nome=nome,
        site=site,
        cidade="Sao Paulo",
        estado="SP",
        pais="Brasil",
        categoria="Fintech",
        descricao_curta="Plataforma de dados.",
        logo_url=None,
        link_perfil_cubo=f"https://cubo.itau/startups-portfolio/{nome.lower()}",
    )


def test_discovery_curates_and_imports_without_counting_existing_as_new():
    persistence = FakePersistence()
    batch_repository = FakeBatchRepository()
    collector = lambda **_: (
        [_startup("Nova", "https://nova.example"), _startup("Existente", "https://existente.example")],
        [],
    )
    service = StartupDiscoveryService(
        persistence,
        collector=collector,
        batch_repository=batch_repository,
    )

    result = service.discover(10, offset=50)

    assert result["collected_count"] == 2
    assert result["curated_count"] == 2
    assert result["created_count"] == 1
    assert result["existing_count"] == 1
    assert result["source_offset"] == 50
    assert persistence.saved[0]["external_id"]
    assert persistence.saved[0]["metadata"]["origem"] == "cubo_portfolio"
    assert result["batch_id"] == str(batch_repository.batch_id)
    assert result["analysis_queued_count"] == 1
    assert [item["nome"] for item in batch_repository.startups] == ["Nova"]


def test_discovery_preserves_collection_errors_and_partial_status():
    persistence = FakePersistence()
    collector = lambda **_: (
        [_startup("Nova", "https://nova.example")],
        [{"startup_index": 0, "mensagem": "cidade nao encontrada"}],
    )

    result = StartupDiscoveryService(
        persistence,
        collector=collector,
        batch_repository=FakeBatchRepository(),
    ).discover(5)

    assert result["status"] == "partial"
    assert result["errors"][0]["startup_index"] == 0
