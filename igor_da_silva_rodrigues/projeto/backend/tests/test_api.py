from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.routes.dependencies import (
    get_batch_service,
    get_persistence,
    get_startup_discovery_service,
)


AUTH = {"X-API-Key": "test-api-key"}


class FakeBatchRepository:
    def __init__(self):
        self.batch_id = uuid4()
        self.batch = {
            "id": str(self.batch_id),
            "status": "pending",
            "total_items": 2,
            "processed_items": 0,
        }
        self.items = [{"id": str(uuid4()), "startup_name": "Alpha", "status": "pending"}]

    def get_batch(self, batch_id):
        return dict(self.batch)

    def list_items(self, batch_id, statuses=None):
        return list(self.items)

    def list_batches(self, limit=20):
        return [dict(self.batch)]

    def cancel_batch(self, batch_id):
        self.batch["status"] = "cancelled"

    def fail_batch(self, batch_id, error):
        self.batch["status"] = "failed"


class FakeBatchService:
    def __init__(self):
        self.repository = FakeBatchRepository()
        self.runs = []

    def create_batch(self, source_file, options):
        return self.repository.batch_id

    def run_batch(self, batch_id, resume=False):
        self.runs.append((batch_id, resume))
        self.repository.batch["status"] = "completed"
        return self.repository.batch


class FakeDiscoveryService:
    def discover(self, limit, offset=0):
        return {
            "status": "success",
            "source": "Cubo Itau - Vitrine de Startups",
            "requested_limit": limit,
            "source_offset": offset,
            "collected_count": limit,
            "curated_count": limit,
            "created_count": 3,
            "existing_count": limit - 3,
            "startup_ids": [],
            "errors": [],
        }


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def select(self, *args): return self
    def order(self, *args, **kwargs): return self
    def range(self, start, end): self.rows = self.rows[start:end + 1]; return self
    def eq(self, field, value): self.rows = [row for row in self.rows if str(row.get(field)) == str(value)]; return self
    def in_(self, field, values): self.rows = [row for row in self.rows if str(row.get(field)) in {str(value) for value in values}]; return self
    def limit(self, value): self.rows = self.rows[:value]; return self
    def execute(self):
        class Response: pass
        response = Response()
        response.data = self.rows
        return response


class FakeDatabase:
    def table(self, name):
        if name == "startups":
            return FakeQuery([{"id": str(uuid4()), "nome": "Alpha"}])
        return FakeQuery([])


class FakePersistence:
    db = FakeDatabase()


class RunDatabase:
    def __init__(self, run_id):
        self.run_id = str(run_id)
        self.source_id = str(uuid4())

    def table(self, name):
        if name == "pipeline_runs":
            return FakeQuery([{"id": self.run_id, "status": "completed"}])
        if name == "inception_fit_assessments":
            return FakeQuery(
                [
                    {
                        "id": str(uuid4()),
                        "pipeline_run_id": self.run_id,
                        "eligibility_status": "unknown",
                        "startup_stage": "unknown",
                        "fit_json": {"open_questions": ["Confirmar elegibilidade."]},
                    }
                ]
            )
        if name == "ai_assessments":
            return FakeQuery(
                [
                    {
                        "id": str(uuid4()),
                        "pipeline_run_id": self.run_id,
                        "classificacao": "AI-enabled",
                        "nivel_maturidade": 3,
                        "confianca_classificacao": 0.8,
                        "tecnologias_utilizadas": {"modelos_apis": ["LLM"]},
                        "justificativa": "Evidencias publicas qualificadas.",
                    }
                ]
            )
        if name == "nvidia_recommendations":
            return FakeQuery(
                [
                    {
                        "id": str(uuid4()),
                        "pipeline_run_id": self.run_id,
                        "fit_score": 0.86,
                        "recomendacao_json": {
                            "recomendacoes": [
                                {
                                    "tecnologia": "Triton",
                                    "fit_score": 0.86,
                                    "justificativa": "Escala de inferencia.",
                                    "dores_atendidas": ["latencia"],
                                }
                            ]
                        },
                    }
                ]
            )
        if name == "evidences":
            return FakeQuery(
                [
                    {
                        "id": str(uuid4()),
                        "pipeline_run_id": self.run_id,
                        "source_id": self.source_id,
                        "trecho": "A startup utiliza machine learning.",
                        "score_confianca": 0.9,
                        "classificacao": "alta",
                        "contem_ia": True,
                        "descartada": False,
                        "motivo_descarte": None,
                    }
                ]
            )
        if name == "sources":
            return FakeQuery(
                [
                    {
                        "id": self.source_id,
                        "url": "https://example.com/evidencia",
                        "tipo_fonte": "oficial",
                        "credibilidade": 0.9,
                        "status": "coletada",
                    }
                ]
            )
        return FakeQuery([])


def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_discover_startups_imports_a_controlled_batch(monkeypatch):
    monkeypatch.setenv("BACKEND_API_KEY", "test-api-key")
    app.dependency_overrides[get_startup_discovery_service] = lambda: FakeDiscoveryService()
    app.dependency_overrides[get_persistence] = lambda: FakePersistence()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/startups/discover",
                json={"limit": 10, "offset": 50},
                headers=AUTH,
            )
        assert response.status_code == 200
        assert response.json()["created_count"] == 3
        assert response.json()["existing_count"] == 7
        assert response.json()["source_offset"] == 50
    finally:
        app.dependency_overrides.clear()


def test_discover_startups_rejects_limit_above_safety_cap(monkeypatch):
    monkeypatch.setenv("BACKEND_API_KEY", "test-api-key")
    app.dependency_overrides[get_startup_discovery_service] = lambda: FakeDiscoveryService()
    app.dependency_overrides[get_persistence] = lambda: FakePersistence()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/startups/discover",
                json={"limit": 50},
                headers=AUTH,
            )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_cors_preflight_allows_local_frontend():
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/startups",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_preflight_rejects_unknown_origin():
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/startups",
            headers={
                "Origin": "https://untrusted.example",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_create_batch_queues_for_external_worker(monkeypatch):
    monkeypatch.setenv("BACKEND_API_KEY", "test-api-key")
    service = FakeBatchService()
    app.dependency_overrides[get_batch_service] = lambda: service
    app.dependency_overrides[get_persistence] = lambda: FakePersistence()
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/batches", json={"limit": 2}, headers=AUTH)
        assert response.status_code == 202
        assert service.runs == []
    finally:
        app.dependency_overrides.clear()


def test_list_startups_uses_backend_persistence(monkeypatch):
    monkeypatch.setenv("BACKEND_API_KEY", "test-api-key")
    app.dependency_overrides[get_persistence] = lambda: FakePersistence()
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/startups", headers=AUTH)
        assert response.status_code == 200
        assert response.json()[0]["nome"] == "Alpha"
    finally:
        app.dependency_overrides.clear()


def test_protected_endpoint_rejects_missing_api_key(monkeypatch):
    monkeypatch.setenv("BACKEND_API_KEY", "test-api-key")
    app.dependency_overrides[get_persistence] = lambda: FakePersistence()
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/startups")
        assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_run_detail_exposes_inception_fit(monkeypatch):
    monkeypatch.setenv("BACKEND_API_KEY", "test-api-key")
    run_id = uuid4()
    persistence = type("Persistence", (), {"db": RunDatabase(run_id)})()
    app.dependency_overrides[get_persistence] = lambda: persistence
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/runs/{run_id}", headers=AUTH)
        assert response.status_code == 200
        assert response.json()["inception_fit"]["eligibility_status"] == "unknown"
        assert response.json()["assessment"]["maturity_class"] == "AI-enabled"
        assert response.json()["assessment"]["technologies"] == ["LLM"]
        recommendation = response.json()["recommendation"]
        assert recommendation["technologies"][0]["name"] == "NVIDIA Triton Inference Server"
        assert recommendation["technologies"][0]["priority"] == "high"
        assert recommendation["opportunity_score"] == 8.6
    finally:
        app.dependency_overrides.clear()


def test_run_evidences_include_traceable_source(monkeypatch):
    monkeypatch.setenv("BACKEND_API_KEY", "test-api-key")
    run_id = uuid4()
    persistence = type("Persistence", (), {"db": RunDatabase(run_id)})()
    app.dependency_overrides[get_persistence] = lambda: persistence
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/runs/{run_id}/evidences", headers=AUTH)
        assert response.status_code == 200
        payload = response.json()
        assert payload[0]["score_confianca"] == 0.9
        assert payload[0]["source"]["url"] == "https://example.com/evidencia"
    finally:
        app.dependency_overrides.clear()


def test_poc_blueprint_exposes_measurable_plan(monkeypatch):
    monkeypatch.setenv("BACKEND_API_KEY", "test-api-key")
    run_id = uuid4()
    persistence = type("Persistence", (), {"db": RunDatabase(run_id)})()
    app.dependency_overrides[get_persistence] = lambda: persistence
    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/runs/{run_id}/poc-blueprint",
                headers=AUTH,
            )
        assert response.status_code == 200
        payload = response.json()
        assert payload["baseline_checklist"]
        assert payload["timeline"]
        assert "workstreams" in payload
        assert "# NVIDIA POC Blueprint" in payload["markdown"]
    finally:
        app.dependency_overrides.clear()


def test_metrics_are_exposed_with_authentication(monkeypatch):
    monkeypatch.setenv("METRICS_BEARER_TOKEN", "test-metrics-token")
    app.dependency_overrides[get_persistence] = lambda: FakePersistence()
    try:
        with TestClient(app) as client:
            response = client.get(
                "/metrics", headers={"Authorization": "Bearer test-metrics-token"}
            )
        assert response.status_code == 200
        assert "nvidia_radar_pipeline_runs_total" not in response.text
    finally:
        app.dependency_overrides.clear()


def test_dashboard_metrics_follow_frontend_contract(monkeypatch):
    monkeypatch.setenv("BACKEND_API_KEY", "test-api-key")
    app.dependency_overrides[get_persistence] = lambda: FakePersistence()
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/metrics", headers=AUTH)
        assert response.status_code == 200
        payload = response.json()
        assert payload["total_startups"] == 1
        assert payload["total_runs"] == 0
        assert payload["success_rate"] == 0
        assert payload["maturity_distribution"] == {"unknown": 1}
    finally:
        app.dependency_overrides.clear()
