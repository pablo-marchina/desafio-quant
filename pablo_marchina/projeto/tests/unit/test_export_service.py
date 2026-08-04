from __future__ import annotations

from pathlib import Path

import pytest

from src.database.session import configure_product_database, reset_product_database_runtime
from src.repositories.export import ExportRepository
from src.repositories.product import ProductRepository
from src.services.product.export_service import ExportService, _content_hash


@pytest.fixture
def setup(tmp_path: Path) -> tuple[ProductRepository, ExportRepository, str]:
    runtime = configure_product_database(f"sqlite:///{(tmp_path / 'export.db').as_posix()}")
    session = runtime.session_factory()
    product_repo = ProductRepository(session)
    export_repo = ExportRepository(session)

    startup = product_repo.create_startup(
        name="Export Test",
        website="https://export.example.com",
        country="Brazil",
        sector="AI",
        description="Export test startup",
        product_summary="Export test summary",
    )
    run = product_repo.create_analysis_run(
        startup_id=startup.id,
        input_snapshot={},
        pipeline_version="test",
        corpus_version=None,
        config_snapshot={},
    )
    product_repo.save_action_brief(
        analysis_run_id=run.id,
        version=1,
        schema_version="2.0",
        brief_json={"startup_name": "Export Test", "recommended_motion": "immediate_outreach"},
        brief_markdown="# Export Test\n\nRecommended: immediate outreach",
    )
    product_repo.session.commit()
    yield product_repo, export_repo, run.id
    session.close()
    reset_product_database_runtime()


def test_content_hash_deterministic() -> None:
    data = {"key": "value", "nested": [1, 2, 3]}
    h1 = _content_hash(data)
    h2 = _content_hash(data)
    assert h1 == h2
    assert isinstance(h1, str)
    assert len(h1) == 64


def test_content_hash_differs_for_different_data() -> None:
    h1 = _content_hash({"a": 1})
    h2 = _content_hash({"a": 2})
    assert h1 != h2


def test_export_service_json(setup: tuple[ProductRepository, ExportRepository, str]) -> None:
    product_repo, export_repo, run_id = setup
    svc = ExportService(
        repository=export_repo,
        product_repo=product_repo,
        product_data_dir=str(Path.cwd() / "test_exports"),
    )
    export = svc.create_export(run_id, "json")
    assert export.export_type == "json"
    assert export.status == "completed"
    assert export.storage_path != ""
    assert export.content_hash != ""


def test_export_service_markdown(setup: tuple[ProductRepository, ExportRepository, str]) -> None:
    product_repo, export_repo, run_id = setup
    svc = ExportService(
        repository=export_repo,
        product_repo=product_repo,
        product_data_dir=str(Path.cwd() / "test_exports"),
    )
    export = svc.create_export(run_id, "markdown")
    assert export.export_type == "markdown"
    assert export.status == "completed"
    assert export.storage_path != ""


def test_export_fails_for_nonexistent_run(
    setup: tuple[ProductRepository, ExportRepository, str],
) -> None:
    _, export_repo, _ = setup
    svc = ExportService(
        repository=export_repo,
        product_repo=ProductRepository.__new__(ProductRepository),
        product_data_dir="test_exports",
    )
    import types

    def fake_get_analysis_run(*args, **kwargs):
        return None

    svc.product_repo.get_analysis_run = types.MethodType(fake_get_analysis_run, svc.product_repo)

    with pytest.raises(LookupError):
        svc.create_export("nonexistent-run", "json")


def test_export_does_not_reference_demo_runs() -> None:
    import inspect

    source = inspect.getsource(ExportService)
    assert "data/demo_runs" not in source
