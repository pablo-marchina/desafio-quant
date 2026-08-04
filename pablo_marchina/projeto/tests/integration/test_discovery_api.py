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
    db_url = f"sqlite:///{(tmp_path / 'disc_api.db').as_posix()}"
    monkeypatch.setenv("PRODUCT_DB_URL", db_url)
    configure_product_database(db_url)
    with TestClient(app) as test_client:
        yield test_client
    reset_product_database_runtime()


@pytest.mark.integration
class TestDiscoverySources:
    def test_list_sources(self, client: TestClient) -> None:
        resp = client.get("/discovery/sources")
        assert resp.status_code == 200
        sources = resp.json()
        assert isinstance(sources, list)
        assert len(sources) >= 1  # at least manual_seed
        source_ids = {s["source_id"] for s in sources}
        assert "manual_seed_br_ai_startups" in source_ids
        assert all("source_id" in s for s in sources)


@pytest.mark.integration
class TestManualSeedDiscovery:
    def test_discover_manual_seed(self, client: TestClient) -> None:
        payload = {
            "entries": [
                {
                    "name": "Radar AI",
                    "website": "https://radar.ai",
                    "sector": "Enterprise AI",
                    "description": "GPU-accelerated ML inference platform",
                    "country": "Brazil",
                },
                {
                    "name": "NLP Brasil",
                    "website": "https://nlpbrasil.example.com",
                    "sector": "NLP",
                    "description": "LLM-powered NLP solutions for Portuguese",
                },
            ]
        }
        resp = client.post("/discovery/manual-seed", json=payload)
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["status"] == "completed"
        assert data["candidates_created"] == 2
        assert data["duplicates_found"] == 0
        assert data["discovery_run_id"] is not None

    def test_manual_seed_dedup_on_repeat(self, client: TestClient) -> None:
        payload = {
            "entries": [
                {
                    "name": "Radar AI",
                    "website": "https://radar.ai",
                    "sector": "AI",
                }
            ]
        }
        r1 = client.post("/discovery/manual-seed", json=payload)
        assert r1.status_code == 201
        r2 = client.post("/discovery/manual-seed", json=payload)
        assert r2.status_code == 201
        assert r2.json()["duplicates_found"] == 1
        assert r2.json()["candidates_created"] == 0

    def test_manual_seed_empty_name_skipped(self, client: TestClient) -> None:
        payload = {
            "entries": [
                {"name": "", "website": "https://no-name.ai", "sector": "AI"},
                {"name": "Valid AI", "website": "https://valid.ai", "sector": "AI"},
            ]
        }
        resp = client.post("/discovery/manual-seed", json=payload)
        assert resp.status_code == 201
        assert resp.json()["candidates_created"] == 1


@pytest.mark.integration
class TestDiscoveryRuns:
    def test_list_and_get_runs(self, client: TestClient) -> None:
        client.post(
            "/discovery/manual-seed",
            json={"entries": [{"name": "Test AI", "sector": "AI"}]},
        )
        list_resp = client.get("/discovery/runs")
        assert list_resp.status_code == 200
        list_data = list_resp.json()
        assert list_data["total"] >= 1
        assert len(list_data["items"]) >= 1

        run_id = list_data["items"][0]["id"]
        get_resp = client.get(f"/discovery/runs/{run_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == run_id

    def test_get_run_not_found(self, client: TestClient) -> None:
        resp = client.get("/discovery/runs/nonexistent")
        assert resp.status_code == 404


@pytest.mark.integration
class TestDiscoveryCandidates:
    def test_list_candidates(self, client: TestClient) -> None:
        client.post(
            "/discovery/manual-seed",
            json={"entries": [{"name": "Candidate AI", "sector": "AI"}]},
        )
        resp = client.get("/discovery/candidates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1
        candidate = data["items"][0]
        assert candidate["discovered_name"] == "Candidate AI"
        assert candidate["confidence"] in ("low", "medium", "high")

    def test_list_candidates_with_filters(self, client: TestClient) -> None:
        client.post(
            "/discovery/manual-seed",
            json={"entries": [{"name": "Filter AI", "sector": "AI"}]},
        )
        resp = client.get("/discovery/candidates?sector=AI")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    def test_get_candidate_detail(self, client: TestClient) -> None:
        client.post(
            "/discovery/manual-seed",
            json={"entries": [{"name": "Detail AI", "sector": "AI"}]},
        )
        list_resp = client.get("/discovery/candidates")
        cid = list_resp.json()["items"][0]["id"]
        get_resp = client.get(f"/discovery/candidates/{cid}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == cid

    def test_get_candidate_not_found(self, client: TestClient) -> None:
        resp = client.get("/discovery/candidates/nonexistent")
        assert resp.status_code == 404


@pytest.mark.integration
class TestCandidatePromote:
    def test_promote_candidate_creates_startup(self, client: TestClient) -> None:
        client.post(
            "/discovery/manual-seed",
            json={
                "entries": [
                    {
                        "name": "Promote AI",
                        "website": "https://promote.ai",
                        "sector": "AI",
                    }
                ]
            },
        )
        list_resp = client.get("/discovery/candidates")
        cid = list_resp.json()["items"][0]["id"]

        promote_resp = client.post(f"/discovery/candidates/{cid}/promote")
        assert promote_resp.status_code == 200, promote_resp.text
        result = promote_resp.json()
        assert result["status"] == "promoted"
        assert result["startup_id"] is not None

        startup_resp = client.get(f"/startups/{result['startup_id']}")
        assert startup_resp.status_code == 200
        assert startup_resp.json()["name"] == "Promote AI"

    def test_promote_twice_returns_already_promoted(self, client: TestClient) -> None:
        client.post(
            "/discovery/manual-seed",
            json={"entries": [{"name": "Double AI", "sector": "AI"}]},
        )
        list_resp = client.get("/discovery/candidates")
        cid = list_resp.json()["items"][0]["id"]

        client.post(f"/discovery/candidates/{cid}/promote")
        r2 = client.post(f"/discovery/candidates/{cid}/promote")
        assert r2.status_code == 200
        assert r2.json()["status"] == "already_promoted"

    def test_promote_nonexistent(self, client: TestClient) -> None:
        resp = client.post("/discovery/candidates/nonexistent/promote")
        assert resp.status_code == 404


@pytest.mark.integration
class TestCandidateDedup:
    def test_dedup_no_duplicate(self, client: TestClient) -> None:
        client.post(
            "/discovery/manual-seed",
            json={"entries": [{"name": "Unique AI", "sector": "AI"}]},
        )
        list_resp = client.get("/discovery/candidates")
        cid = list_resp.json()["items"][0]["id"]
        resp = client.post(f"/discovery/candidates/{cid}/dedup")
        assert resp.status_code == 200
        assert resp.json()["duplicate_of_candidate_id"] is None
        assert resp.json()["duplicate_of_startup_id"] is None
