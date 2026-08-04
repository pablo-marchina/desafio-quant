"""Product Golden Path — End-to-End Acceptance Tests.

Validates the complete product flow from readiness through export.
These tests use FastAPI TestClient with a temporary SQLite database.
They do NOT require Qdrant, RAG, or any external services.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.database.session import configure_product_database, reset_product_database_runtime

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "product_golden_path"


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    db_url = f"sqlite:///{(tmp_path / 'golden_path.db').as_posix()}"
    monkeypatch.setenv("PRODUCT_DB_URL", db_url)
    monkeypatch.setenv("APP_MODE", "test")
    monkeypatch.setenv("ENABLE_PRODUCT_PERSISTENCE", "true")
    monkeypatch.setenv("QDRANT_URL", "")
    monkeypatch.setenv("RAG_REQUIRED_FOR_PRODUCT", "false")
    monkeypatch.setenv("PRODUCT_DATA_DIR", str(tmp_path / "product_data"))
    configure_product_database(db_url)
    with TestClient(app) as test_client:
        yield test_client
    reset_product_database_runtime()


def _load_fixture(name: str) -> dict:
    path = FIXTURE_DIR / name
    if not path.exists():
        pytest.skip(f"Fixture not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.acceptance
class TestProductReadinessContract:
    def test_readiness_returns_ready(self, client: TestClient) -> None:
        resp = client.get("/product/readiness")
        assert resp.status_code == 200
        data = resp.json()
        assert "ready" in data
        assert "blocking_missing_config" in data
        assert "setup_checklist" in data
        assert "user_messages" in data

    def test_readiness_has_bool_ready(self, client: TestClient) -> None:
        resp = client.get("/product/readiness")
        assert isinstance(resp.json()["ready"], bool)


@pytest.mark.acceptance
class TestProductCapabilitiesContract:
    def test_capabilities_count(self, client: TestClient) -> None:
        expected = _load_fixture("expected.json")
        resp = client.get("/product/capabilities")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= expected["min_capabilities"]

    def test_capabilities_have_required_fields(self, client: TestClient) -> None:
        resp = client.get("/product/capabilities")
        data = resp.json()
        for cap in data:
            assert "capability_id" in cap
            assert "name" in cap
            assert "status" in cap
            assert "category" in cap
            assert "required" in cap


@pytest.mark.acceptance
class TestProductGoldenPathBackend:
    """Full Product Golden Path: startup through export."""

    def _create_startup(self, client: TestClient) -> dict:
        startup = _load_fixture("startup.json")
        resp = client.post("/startups", json=startup)
        assert resp.status_code == 201, f"Create startup failed: {resp.text}"
        return resp.json()

    def _create_analysis_run(self, client: TestClient, startup_id: str) -> dict:
        resp = client.post(
            f"/startups/{startup_id}/analysis-runs",
            json={"use_rag": False},
        )
        assert resp.status_code == 201, f"Create analysis run failed: {resp.text}"
        data = resp.json()
        assert data["status"] in {"completed", "degraded"}, f"Unexpected status: {data['status']}"
        assert len(data["scores"]) == 4
        assert data["action_brief_id"] is not None
        return data

    def test_golden_path_full(self, client: TestClient) -> None:
        expected = _load_fixture("expected.json")

        startup = self._create_startup(client)
        assert startup["normalized_name"] == "golden path ai"
        assert len(startup["evidence"]) >= 3

        listed = client.get("/startups")
        assert listed.status_code == 200
        ids = {s["id"] for s in listed.json()}
        assert startup["id"] in ids

        patch_resp = client.patch(
            f"/startups/{startup['id']}",
            json={"sector": "AI/ML Infrastructure"},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["sector"] == "AI/ML Infrastructure"
        assert len(patch_resp.json()["evidence"]) >= 3

        run = self._create_analysis_run(client, startup["id"])
        assert run["startup_id"] == startup["id"]

        fetched_run = client.get(f"/analysis-runs/{run['id']}")
        assert fetched_run.status_code == 200
        fetched_run_data = fetched_run.json()
        assert fetched_run_data["run_id"] == run["id"]
        assert fetched_run_data["startup_id"] == startup["id"]
        assert fetched_run_data["action_brief"] is not None

        claims_resp = client.get(f"/analysis-runs/{run['id']}/claims")
        assert claims_resp.status_code == 200
        claims_data = claims_resp.json()
        assert claims_data["total"] >= expected["min_claims"]

        coverage_resp = client.get(f"/analysis-runs/{run['id']}/evidence-coverage")
        assert coverage_resp.status_code == 200
        coverage = coverage_resp.json()
        assert coverage["total_claims"] > 0

        act_gen = client.post(f"/analysis-runs/{run['id']}/activation-recommendations/generate")
        assert act_gen.status_code == 201
        act_data = act_gen.json()
        assert act_data["total"] >= expected["min_activation_recommendations"]

        act_list = client.get(f"/analysis-runs/{run['id']}/activation-recommendations")
        assert act_list.status_code == 200
        assert act_list.json()["total"] >= expected["min_activation_recommendations"]

        dossier_resp = client.post(f"/analysis-runs/{run['id']}/dossier")
        assert dossier_resp.status_code == 201
        dossier_data = dossier_resp.json()
        assert dossier_data["is_new"] is True
        assert dossier_data["version"] == expected["dossier_version_expected"]
        dossier = dossier_data["dossier"]
        assert dossier["analysis_run_id"] == run["id"]
        if expected["dossier_has_json"]:
            assert dossier["dossier_json"] is not None
        if expected["dossier_has_markdown"]:
            assert dossier["dossier_markdown"] is not None

        dossier_get = client.get(f"/analysis-runs/{run['id']}/dossier")
        assert dossier_get.status_code == 200
        assert dossier_get.json()["is_latest"] is True

        dossier_md = client.get(f"/analysis-runs/{run['id']}/dossier/markdown")
        assert dossier_md.status_code == 200
        assert "# Startup Activation Dossier" in dossier_md.json()["markdown"]

        quality_resp = client.post(f"/analysis-runs/{run['id']}/quality-runs")
        assert quality_resp.status_code == 201
        quality_data = quality_resp.json()
        assert quality_data["analysis_run_id"] == run["id"]
        assert quality_data["status"] in {"completed", "degraded"}
        assert len(quality_data["metrics"]) >= expected["quality_metrics_min"]

        quality_summary = client.get(f"/analysis-runs/{run['id']}/quality-summary")
        assert quality_summary.status_code == 200
        qs = quality_summary.json()
        assert qs["overall_status"] in expected["quality_status_options"]

        opp_resp = client.get("/opportunities")
        assert opp_resp.status_code == 200
        opp_data = opp_resp.json()
        assert opp_data["total"] >= expected["opportunities_min_items"]
        item_ids = {item["startup_id"] for item in opp_data["items"]}
        assert startup["id"] in item_ids

        export_resp = client.post(
            f"/analysis-runs/{run['id']}/exports",
            json={"export_type": expected["export_type"]},
        )
        assert export_resp.status_code == 201
        export_data = export_resp.json()
        assert export_data["export_type"] == expected["export_type"]
        assert export_data["status"] == expected["export_status"]
        assert export_data["content_hash"] != ""


@pytest.mark.acceptance
class TestProductDossierAcceptance:
    def test_dossier_idempotent(self, client: TestClient) -> None:
        startup = _load_fixture("startup.json")
        created = client.post("/startups", json=startup).json()
        run = client.post(f"/startups/{created['id']}/analysis-runs", json={"use_rag": False}).json()

        r1 = client.post(f"/analysis-runs/{run['id']}/dossier").json()
        r2 = client.post(f"/analysis-runs/{run['id']}/dossier").json()

        assert r2["is_new"] is False
        assert r2["dossier"]["id"] == r1["dossier"]["id"]

    def test_dossier_force_new_version(self, client: TestClient) -> None:
        startup = _load_fixture("startup.json")
        created = client.post("/startups", json=startup).json()
        run = client.post(f"/startups/{created['id']}/analysis-runs", json={"use_rag": False}).json()

        r1 = client.post(f"/analysis-runs/{run['id']}/dossier").json()["dossier"]
        r2 = client.post(f"/analysis-runs/{run['id']}/dossier?force=true").json()["dossier"]

        assert r2["id"] != r1["id"]
        assert r2["version"] == 2
        assert r2["is_latest"] is True

    def test_dossier_404_for_nonexistent_run(self, client: TestClient) -> None:
        assert client.post("/analysis-runs/nonexistent/dossier").status_code == 404
        assert client.get("/analysis-runs/nonexistent/dossier").status_code == 404


@pytest.mark.acceptance
class TestProductQualityAcceptance:
    def test_quality_run_lifecycle(self, client: TestClient) -> None:
        startup = _load_fixture("startup.json")
        created = client.post("/startups", json=startup).json()
        run = client.post(f"/startups/{created['id']}/analysis-runs", json={"use_rag": False}).json()

        quality = client.post(f"/analysis-runs/{run['id']}/quality-runs").json()

        latest = client.get(f"/analysis-runs/{run['id']}/quality-runs/latest")
        assert latest.status_code == 200
        assert latest.json()["id"] == quality["id"]

        listing = client.get(f"/analysis-runs/{run['id']}/quality-runs")
        assert listing.status_code == 200
        assert len(listing.json()) == 1

        no_run = client.get(f"/analysis-runs/{run['id']}/quality-runs/latest")
        assert no_run.status_code == 200

    def test_quality_summary_without_quality_run(self, client: TestClient) -> None:
        startup = _load_fixture("startup.json")
        created = client.post("/startups", json=startup).json()
        run = client.post(f"/startups/{created['id']}/analysis-runs", json={"use_rag": False}).json()

        summary = client.get(f"/analysis-runs/{run['id']}/quality-summary")
        assert summary.status_code == 200
        assert summary.json()["overall_status"] == "no_quality_run"
        assert summary.json()["quality_run_id"] is None


@pytest.mark.acceptance
class TestProductOpportunitiesAcceptance:
    def test_opportunities_filters(self, client: TestClient) -> None:
        startup = _load_fixture("startup.json")
        created = client.post("/startups", json=startup).json()
        client.post(f"/startups/{created['id']}/analysis-runs", json={"use_rag": False})

        resp = client.get("/opportunities?limit=10&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["offset"] == 0
        assert data["limit"] == 10
