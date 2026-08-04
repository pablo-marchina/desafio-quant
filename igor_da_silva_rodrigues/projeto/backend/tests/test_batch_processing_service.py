import json

from app.persistence.batch_repository import BatchRepository
from app.persistence.persistence_service import PipelinePersistence
from app.services.batch_processing_service import (
    BatchExecutionOptions,
    BatchProcessingService,
    CuratedStartupLoader,
)
from tests.test_persistence_service import FakeSupabase


def _write_curated(path):
    startups = [
        {
            "startup_id": "cubo_alpha_1",
            "nome": "Alpha",
            "site": "https://alpha.example",
            "categoria": "Fintech",
            "decisao_pipeline": {"prosseguir": True},
        },
        {
            "startup_id": "cubo_beta_2",
            "nome": "Beta",
            "site": "https://beta.example",
            "categoria": "Healthtech",
            "decisao_pipeline": {"prosseguir": False},
        },
    ]
    file = path / "curated.json"
    file.write_text(json.dumps({"startups": startups}), encoding="utf-8")
    return file


def test_batch_service_processes_items_and_isolates_failure(tmp_path):
    _write_curated(tmp_path)
    repository = BatchRepository(PipelinePersistence(client=FakeSupabase()))

    def runner(payload):
        if payload["startup_name"] == "Beta":
            raise RuntimeError("Fonte indisponivel")
        return {
            "status": "completo",
            "classificacao": "AI-enabled",
            "nivel_maturidade": 3,
            "impacto_estimado": {"indice_impacto_agregado": 80},
            "briefing_markdown": "# Briefing",
            "pipeline_run_id": None,
            "errors": [],
        }

    service = BatchProcessingService(
        repository,
        loader=CuratedStartupLoader(tmp_path),
        pipeline_runner=runner,
    )
    batch_id = service.create_batch("curated.json")
    result = service.run_batch(batch_id)

    assert result["status"] == "partial"
    assert result["processed_items"] == 2
    assert result["succeeded_items"] == 1
    assert result["failed_items"] == 1
    items = repository.list_items(batch_id)
    assert items[0]["result_summary"]["briefing_disponivel"] is True
    assert items[1]["last_error"] == "Fonte indisponivel"


def test_batch_service_retries_transient_failure_automatically(tmp_path):
    _write_curated(tmp_path)
    repository = BatchRepository(PipelinePersistence(client=FakeSupabase()))
    attempts = {"count": 0}

    def runner(payload):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("Falha transitoria")
        return {"status": "completo", "pipeline_run_id": None, "errors": []}

    service = BatchProcessingService(
        repository,
        loader=CuratedStartupLoader(tmp_path),
        pipeline_runner=runner,
    )
    batch_id = service.create_batch(
        "curated.json",
        BatchExecutionOptions(limit=1, max_attempts=2),
    )
    assert service.run_batch(batch_id)["status"] == "completed"
    assert repository.list_items(batch_id)[0]["attempt_count"] == 2


def test_batch_service_moves_exhausted_failure_to_dead_letter(tmp_path):
    _write_curated(tmp_path)
    repository = BatchRepository(PipelinePersistence(client=FakeSupabase()))
    service = BatchProcessingService(
        repository,
        loader=CuratedStartupLoader(tmp_path),
        pipeline_runner=lambda payload: (_ for _ in ()).throw(RuntimeError("Falha permanente")),
    )
    batch_id = service.create_batch(
        "curated.json",
        BatchExecutionOptions(limit=1, max_attempts=2),
    )

    result = service.run_batch(batch_id)
    letters = repository.list_dead_letters(batch_id)

    assert result["status"] == "failed"
    assert repository.list_items(batch_id)[0]["attempt_count"] == 2
    assert len(letters) == 1
    assert letters[0]["last_error"] == "Falha permanente"


def test_curated_loader_filters_ineligible_startups(tmp_path):
    _write_curated(tmp_path)
    loader = CuratedStartupLoader(tmp_path)
    _, startups = loader.load("curated.json")

    selected = loader.select(
        startups,
        BatchExecutionOptions(include_ineligible=False),
    )

    assert [item["nome"] for item in selected] == ["Alpha"]


def test_batch_service_rejects_duplicate_start(tmp_path):
    _write_curated(tmp_path)
    repository = BatchRepository(PipelinePersistence(client=FakeSupabase()))
    service = BatchProcessingService(
        repository,
        loader=CuratedStartupLoader(tmp_path),
        pipeline_runner=lambda payload: {"status": "completo", "errors": []},
    )
    batch_id = service.create_batch("curated.json", {"limit": 1})
    repository.start_batch(batch_id)

    try:
        service.run_batch(batch_id)
    except ValueError as exc:
        assert "ja esta em execucao" in str(exc)
    else:
        raise AssertionError("Inicio duplicado deveria ser rejeitado")
