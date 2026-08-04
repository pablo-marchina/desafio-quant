from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.database.session import configure_product_database, reset_product_database_runtime
from src.services.product.service import ProductService


@pytest.fixture
def service(tmp_path: Path) -> ProductService:
    runtime = configure_product_database(f"sqlite:///{(tmp_path / 'service.db').as_posix()}")
    session = runtime.session_factory()
    yield ProductService(session)
    session.close()
    reset_product_database_runtime()


def _startup_payload() -> dict[str, Any]:
    return {
        "name": "Product Startup",
        "website": "https://product.example.com",
        "country": "Brazil",
        "sector": "AI Infrastructure",
        "description": "Production AI platform",
        "product_summary": "Optimizes inference workloads",
        "evidence": [
            {
                "claim": "Runs inference in production",
                "source_url": "https://product.example.com/technology",
                "source_type": "official_site",
                "quote_or_evidence": ("Our platform runs GPU inference workloads in production environments."),
                "confidence": "high",
            }
        ],
    }


def test_product_service_persists_real_pipeline_outputs(service: ProductService) -> None:
    startup = service.create_startup(_startup_payload())

    run = service.create_analysis_run_for_startup(startup.id, use_rag=False)

    assert run.status in {"completed", "degraded"}
    assert len(run.scores) == 4
    assert run.briefs
    assert run.output_snapshot_json["startup_name"] == startup.name
    assert service.get_action_brief_for_run(run.id) is not None


def test_product_service_persists_failed_run_without_fallback(
    service: ProductService,
) -> None:
    startup = service.create_startup(_startup_payload())

    def failing_pipeline(**_: Any) -> Any:
        raise RuntimeError("controlled pipeline failure")

    service.pipeline_runner = failing_pipeline
    run = service.create_analysis_run_for_startup(startup.id, use_rag=False)

    assert run.status == "failed"
    assert run.error_message == "controlled pipeline failure"
    assert run.output_snapshot_json == {}
    assert not run.briefs


def test_product_service_blocks_non_rag_analysis_in_product_mode(
    service: ProductService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    startup = service.create_startup(_startup_payload())
    monkeypatch.setenv("APP_MODE", "product")
    monkeypatch.setenv("RAG_REQUIRED_FOR_PRODUCT", "true")

    with pytest.raises(ValueError, match="requires use_rag=true"):
        service.create_analysis_run_for_startup(startup.id, use_rag=False)


def test_product_service_blocks_non_qdrant_rag_backend_in_product_mode(
    service: ProductService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    startup = service.create_startup(_startup_payload())
    monkeypatch.setenv("APP_MODE", "product")
    monkeypatch.setenv("RAG_REQUIRED_FOR_PRODUCT", "true")

    with pytest.raises(ValueError, match="requires rag_backend='qdrant'"):
        service.create_analysis_run_for_startup(startup.id, use_rag=True, rag_backend="local")


def test_product_modules_do_not_reference_demo_runs() -> None:
    product_paths = [
        Path("src/database"),
        Path("src/repositories"),
        Path("src/services/product"),
        Path("src/api/product_routes.py"),
    ]
    contents = "\n".join(
        file.read_text(encoding="utf-8")
        for path in product_paths
        for file in ([path] if path.is_file() else path.rglob("*.py"))
    )

    assert "data/demo_runs" not in contents
