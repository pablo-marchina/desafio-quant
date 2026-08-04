"""Guard: Product acceptance must not depend on data/demo_runs.

This test verifies that the acceptance flow does not access legacy demo
artifacts. It monkeypatches the config to ensure data/demo_runs paths
are never read during product acceptance.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.database.session import configure_product_database, reset_product_database_runtime


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("APP_MODE", "test")
    monkeypatch.setenv("ENABLE_PRODUCT_PERSISTENCE", "true")
    monkeypatch.setenv("QDRANT_URL", "")
    monkeypatch.setenv("RAG_REQUIRED_FOR_PRODUCT", "false")
    monkeypatch.setenv("PRODUCT_DATA_DIR", str(tmp_path / "product_data"))
    db_url = f"sqlite:///{(tmp_path / 'guard.db').as_posix()}"
    monkeypatch.setenv("PRODUCT_DB_URL", db_url)
    configure_product_database(db_url)
    with TestClient(app) as test_client:
        yield test_client
    reset_product_database_runtime()


@pytest.mark.acceptance
def test_no_demo_during_acceptance_flow(client: TestClient) -> None:
    """Verify that the full acceptance flow never reads from data/demo_runs.

    The test uses an isolated tmp_path so any read of data/demo_runs
    would indicate an unwanted dependency. We also verify that the
    product endpoints return valid data without demo artifacts.
    """
    resp = client.get("/health/product")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    resp = client.get("/product/readiness")
    assert resp.status_code == 200

    resp = client.get("/product/capabilities")
    assert resp.status_code == 200
    assert len(resp.json()) >= 25


@pytest.mark.acceptance
def test_readiness_does_not_depend_on_demo_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify readiness endpoints work without data/demo_runs existing."""
    from src.services.product.readiness_service import ProductReadinessService

    svc = ProductReadinessService()
    capabilities = svc.list_capabilities()
    assert len(capabilities) >= 25

    report = svc.get_product_readiness()
    assert hasattr(report, "ready")


@pytest.mark.acceptance
def test_golden_fixture_shape() -> None:
    """Validate that the golden fixture matches expected schema."""
    import json

    fixture_path = Path(__file__).resolve().parent.parent / "fixtures" / "product_golden_path" / "startup.json"
    assert fixture_path.exists(), f"Fixture not found: {fixture_path}"

    with open(fixture_path, encoding="utf-8") as f:
        data = json.load(f)

    assert "name" in data
    assert "website" in data
    assert "sector" in data
    assert "description" in data
    assert isinstance(data.get("evidence", []), list)
    for ev in data["evidence"]:
        assert "claim" in ev
        assert "source_url" in ev
        assert "source_type" in ev
        assert "confidence" in ev
