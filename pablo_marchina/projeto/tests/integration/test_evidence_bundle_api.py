from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.database.session import configure_product_database, reset_product_database_runtime


@pytest.fixture
def client_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("APP_MODE", "test")
    monkeypatch.setenv("ENABLE_PRODUCT_PERSISTENCE", "true")
    monkeypatch.setenv("QDRANT_URL", "")
    db_url = f"sqlite:///{(tmp_path / 'evidence_bundle_api.db').as_posix()}"
    monkeypatch.setenv("PRODUCT_DB_URL", db_url)
    configure_product_database(db_url)
    with TestClient(app) as test_client:
        yield test_client
    reset_product_database_runtime()


def _setup_run(client: TestClient, name: str = "Evidence Bundle Startup") -> tuple[str, str]:
    resp = client.post(
        "/startups",
        json={
            "name": name,
            "website": f"https://{name.lower().replace(' ', '-')}.example.com",
            "country": "Brazil",
            "sector": "AI",
            "description": "AI company for evidence bundle testing",
            "product_summary": "AI platform with NVIDIA fit signals",
        },
    )
    assert resp.status_code == 201, resp.text
    startup_id = resp.json()["id"]

    run_resp = client.post(f"/startups/{startup_id}/analysis-runs", json={})
    assert run_resp.status_code == 201, run_resp.text
    return startup_id, run_resp.json()["id"]


def test_evidence_bundle_returns_404_for_unknown_run(client_fixture: TestClient) -> None:
    resp = client_fixture.get("/analysis-runs/not-a-run/evidence-bundle")
    assert resp.status_code == 404


def test_evidence_bundle_returns_core_sections(client_fixture: TestClient) -> None:
    startup_id, run_id = _setup_run(client_fixture, "Evidence Bundle Core")

    resp = client_fixture.get(f"/analysis-runs/{run_id}/evidence-bundle")

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["analysis_run_id"] == run_id
    assert data["startup_id"] == startup_id
    assert data["readiness"] in {"ready", "degraded", "blocked", "failed", "completed"}
    assert data["confidence"] in {"unknown", "low", "medium", "high"}
    assert "evidence_coverage" in data
    assert set(data["claims"]) >= {"supported", "weak", "unsupported", "critical"}
    assert isinstance(data["missing_evidence"], list)
    assert isinstance(data["rag_support"], dict)
    assert "available" in data["rag_support"]
    assert isinstance(data["lineage"], dict)


def test_evidence_bundle_includes_recommendations_dossier_and_lost_alternatives(
    client_fixture: TestClient,
) -> None:
    _, run_id = _setup_run(client_fixture, "Evidence Bundle Recommendations")

    rec_resp = client_fixture.post(f"/analysis-runs/{run_id}/activation-recommendations/generate")
    assert rec_resp.status_code == 201, rec_resp.text
    dossier_resp = client_fixture.post(f"/analysis-runs/{run_id}/dossier")
    assert dossier_resp.status_code == 201, dossier_resp.text

    resp = client_fixture.get(f"/analysis-runs/{run_id}/evidence-bundle")

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data["recommendations"], list)
    assert data["dossier"] is not None
    assert data["lineage"]["dossier_id"] == data["dossier"]["id"]
    assert isinstance(data["alternatives_lost"], list)
    if data["alternatives_lost"]:
        first = data["alternatives_lost"][0]
        assert "playbook_id" in first
        assert "reason_lost" in first
