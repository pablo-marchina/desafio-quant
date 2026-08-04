from __future__ import annotations

from datetime import UTC, datetime
from threading import Event

import pytest
from fastapi.testclient import TestClient

from scraper.api.dependencies import (
    action_report_service,
    pipeline_runner,
    supabase_service,
    technology_intelligence_service,
)
from scraper.api.main import app
from scraper.api.repositories.startup_repository import (
    SupabaseStartupRepository,
)
from scraper.api.schemas import JobStatus
from scraper.api.services.job_manager import JobManager
from scraper.api.services.pipeline_runner import PipelineRunner
from scraper.api.services.startup_service import (
    StartupNotFoundError,
    StartupService,
)


class FakeStartupRepository:
    def __init__(self):
        self.rows = {
            "startup-1": {
                "id": "startup-1",
                "candidate_id": "candidate-1",
                "company_name": "Acme",
            }
        }

    def list(self, **_):
        return list(self.rows.values()), len(self.rows)

    def find_one(self, field, value):
        return next(
            (
                row
                for row in self.rows.values()
                if str(row.get(field)) == value
            ),
            None,
        )

    def count(self, field=None, value=None):
        if field is None:
            return len(self.rows)
        return sum(row.get(field) == value for row in self.rows.values())

    def count_present(self, field):
        return sum(row.get(field) is not None for row in self.rows.values())

    def create(self, data):
        row = {"id": "startup-2", **data}
        self.rows[row["id"]] = row
        return row

    def update(self, record_id, data):
        if record_id not in self.rows:
            return None
        self.rows[record_id] = {**self.rows[record_id], **data}
        return self.rows[record_id]

    def delete(self, record_id):
        return self.rows.pop(record_id, None) is not None


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_job_manager_completes_and_records_result():
    manager = JobManager(max_workers=1)
    finished = Event()

    def operation(progress):
        progress(50)
        finished.set()
        return {"ok": True}

    job = manager.submit("test", "startup-1", operation)
    assert finished.wait(timeout=2)
    manager.shutdown(wait=True)
    current = manager.get(job.job_id)
    assert current is not None
    assert current.status == JobStatus.COMPLETED
    assert current.progress == 100
    assert current.result == {"ok": True}


def test_job_manager_records_failure():
    manager = JobManager(max_workers=1)
    finished = Event()

    def operation(_):
        finished.set()
        raise RuntimeError("pipeline failed")

    job = manager.submit("test", "startup-1", operation)
    assert finished.wait(timeout=2)
    manager.shutdown(wait=True)
    current = manager.get(job.job_id)
    assert current is not None
    assert current.status == JobStatus.FAILED
    assert current.error == "pipeline failed"
    assert current.finished_at is not None


def test_company_registration_runner_uses_only_cnpj_flow(monkeypatch):
    saved_states = []
    progress_values = []
    candidate = {
        "id": "candidate-1",
        "company_name": "Acme",
        "enrichment_status": "enriched",
    }

    monkeypatch.setattr(
        "scraper.enrichment_pipeline.nodes.update_supabase.load_candidates",
        lambda **_: [candidate],
    )
    monkeypatch.setattr(
        "scraper.enrichment_pipeline.nodes.cnpj_lookup.lookup_cnpj",
        lambda received: {
            "cnpj": "11222333000181",
            "razao_social": "ACME LTDA",
        },
    )
    monkeypatch.setattr(
        "scraper.enrichment_pipeline.nodes.update_supabase.ensure_results_schema",
        lambda: None,
    )
    monkeypatch.setattr(
        "scraper.enrichment_pipeline.nodes.update_supabase.save_enrichment_result",
        saved_states.append,
    )

    result = PipelineRunner().company_registration(
        "candidate-1", progress_values.append
    )

    assert result == {"updated": True, "cnpj": "11222333000181"}
    assert progress_values == [10, 75, 95]
    assert saved_states[0]["candidate"] == candidate
    assert saved_states[0]["cnpj_data"]["razao_social"] == "ACME LTDA"
    assert saved_states[0]["enrichment_status"] == "enriched"


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_list_startups(client, monkeypatch):
    captured = {}

    def fake_list_startups(**kwargs):
        captured.update(kwargs)
        return ([{"id": "1", "company_name": "Acme"}], 1)

    monkeypatch.setattr(
        supabase_service,
        "list_startups",
        fake_list_startups,
    )
    response = client.get(
        "/startups?page=1&page_size=20&has_nvidia_recommendation=true"
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["company_name"] == "Acme"
    assert captured["has_nvidia_recommendation"] is True


def test_enrichment_returns_job_immediately(client, monkeypatch):
    finished = Event()
    monkeypatch.setattr(
        supabase_service, "resolve_candidate_id", lambda _: "candidate-1"
    )

    def fake_enrich(candidate_id, progress):
        assert candidate_id == "candidate-1"
        progress(50)
        finished.set()
        return {"updated": 1}

    monkeypatch.setattr(pipeline_runner, "enrich", fake_enrich)
    response = client.post("/startups/startup-1/enrich")
    assert response.status_code == 202
    payload = response.json()
    assert payload["job_id"]
    assert payload["status"] in {"queued", "running"}
    assert finished.wait(timeout=2)


def test_company_registration_returns_job_immediately(client, monkeypatch):
    finished = Event()
    monkeypatch.setattr(
        supabase_service, "resolve_candidate_id", lambda _: "candidate-1"
    )

    def fake_company_registration(candidate_id, progress):
        assert candidate_id == "candidate-1"
        progress(75)
        finished.set()
        return {"updated": True, "cnpj": "11222333000181"}

    monkeypatch.setattr(
        pipeline_runner,
        "company_registration",
        fake_company_registration,
    )
    response = client.post(
        "/startups/startup-1/company-registration"
    )
    assert response.status_code == 202
    assert response.json()["job_id"]
    assert finished.wait(timeout=2)


def test_technology_intelligence_returns_job_immediately(client, monkeypatch):
    finished = Event()
    monkeypatch.setattr(
        supabase_service,
        "get_startup",
        lambda _: {"id": "startup-1", "company_name": "Acme"},
    )

    def fake_analyze(startup, progress):
        assert startup["company_name"] == "Acme"
        progress(70)
        finished.set()
        return {"schema_version": "technology-intelligence/v1"}

    monkeypatch.setattr(
        technology_intelligence_service, "analyze", fake_analyze
    )
    response = client.post(
        "/startups/startup-1/technology-intelligence"
    )
    assert response.status_code == 202
    assert response.json()["job_id"]
    assert finished.wait(timeout=2)


def test_action_report_returns_job_immediately(client, monkeypatch):
    finished = Event()
    monkeypatch.setattr(
        supabase_service,
        "get_startup",
        lambda _: {
            "id": "startup-1",
            "company_name": "Acme",
            "nvidia_recommendation": {"recommendations": []},
        },
    )

    def fake_generate(startup, progress, objective=None, context=None):
        assert startup["company_name"] == "Acme"
        assert objective == "priorizar proximos passos"
        assert context == {"produto_alvo": "NIM"}
        progress(70)
        finished.set()
        return {"executive_summary": "Relatorio pronto"}

    monkeypatch.setattr(action_report_service, "generate", fake_generate)
    response = client.post(
        "/startups/startup-1/action-report",
        json={"objective": "priorizar proximos passos", "context": {"produto_alvo": "NIM"}},
    )
    assert response.status_code == 202
    assert response.json()["job_id"]
    assert finished.wait(timeout=2)


def test_unknown_job_returns_404(client):
    response = client.get("/jobs/not-found")
    assert response.status_code == 404


def test_startup_service_crud_uses_repository():
    repository = FakeStartupRepository()
    service = StartupService(
        repository=repository,
        candidate_repository=repository,
    )

    created = service.create_startup(
        {"candidate_id": "candidate-2", "company_name": "Beta"}
    )
    assert created["id"] == "startup-2"

    updated = service.update_startup(
        "startup-2", {"company_name": "Beta AI"}
    )
    assert updated["company_name"] == "Beta AI"

    service.delete_startup("startup-2")
    with pytest.raises(StartupNotFoundError):
        service.get_startup("startup-2")


def test_startup_service_dashboard_summary_uses_aggregated_counts():
    class AggregatedRepository(FakeStartupRepository):
        def __init__(self):
            super().__init__()
            self.summary_called = False

        def dashboard_summary_counts(self):
            self.summary_called = True
            return {
                "total_startups": 2,
                "validation_statuses": {"APPROVED": 1, "REVIEW": 1},
                "enrichment_statuses": {"enriched": 1},
                "ai_classifications": {"AI_ENABLED": 2},
                "recommendations_count": 1,
            }

    repository = AggregatedRepository()
    service = StartupService(
        repository=repository,
        candidate_repository=repository,
    )

    summary = service.dashboard_summary()

    assert repository.summary_called is True
    assert summary["total_startups"] == 2
    assert summary["validation_statuses"] == {"APPROVED": 1, "REVIEW": 1}
    assert summary["recommendations_count"] == 1
    assert len(summary["github_actions_registrations"]) == 8
    assert {
        point["weekday"]
        for point in summary["github_actions_registrations"]
    } == {"Seg", "Qui"}
    assert "generated_at" in summary


def test_startup_service_builds_monday_and_thursday_chart_points():
    points = StartupService._automation_chart_points(
        [
            {"date": "2026-06-22", "count": 4},
            {"date": "2026-06-25", "count": 7},
            {"date": "2026-06-29", "count": 2},
        ],
        datetime(2026, 6, 30, 12, tzinfo=UTC),
    )

    assert [point["date"] for point in points] == [
        "2026-06-04",
        "2026-06-08",
        "2026-06-11",
        "2026-06-15",
        "2026-06-18",
        "2026-06-22",
        "2026-06-25",
        "2026-06-29",
    ]
    assert [point["count"] for point in points][-3:] == [4, 7, 2]


def test_dashboard_summary_uses_candidate_business_classifications():
    class CatalogRepository(FakeStartupRepository):
        def dashboard_summary_counts(self):
            return {
                "total_startups": 3,
                "validation_statuses": {},
                "enrichment_statuses": {},
                "ai_classifications": {"INSUFFICIENT_EVIDENCE": 3},
                "recommendations_count": 0,
                "github_actions_registrations": [],
                "_candidate_ids": ["candidate-1", "candidate-2", "candidate-3"],
            }

    class CandidateRepository(FakeStartupRepository):
        def ai_classification_counts(self, record_ids):
            assert record_ids == {
                "candidate-1",
                "candidate-2",
                "candidate-3",
            }
            return {"AI_NATIVE": 1, "AI_ENABLED": 1, "NON_AI": 1}

    summary = StartupService(
        repository=CatalogRepository(),
        candidate_repository=CandidateRepository(),
    ).dashboard_summary()

    assert summary["ai_classifications"] == {
        "AI_NATIVE": 1,
        "AI_ENABLED": 1,
        "NON_AI": 1,
    }
    assert "_candidate_ids" not in summary


def test_create_startup_endpoint(client, monkeypatch):
    monkeypatch.setattr(
        supabase_service,
        "create_startup",
        lambda data: {"id": "2", **data},
    )
    response = client.post(
        "/startups",
        json={"candidate_id": "candidate-2", "company_name": "Beta"},
    )
    assert response.status_code == 201
    assert response.json()["startup"]["company_name"] == "Beta"


def test_update_and_delete_startup_endpoints(client, monkeypatch):
    monkeypatch.setattr(
        supabase_service,
        "update_startup",
        lambda startup_id, data: {"id": startup_id, **data},
    )
    response = client.patch(
        "/startups/startup-1",
        json={"company_name": "Acme AI"},
    )
    assert response.status_code == 200
    assert response.json()["startup"]["company_name"] == "Acme AI"

    monkeypatch.setattr(
        supabase_service, "delete_startup", lambda startup_id: None
    )
    response = client.delete("/startups/startup-1")
    assert response.status_code == 204
    assert response.content == b""


def test_supabase_repository_rest_crud(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")
    calls = []

    class FakeResponse:
        def __init__(self, payload, headers=None):
            self._payload = payload
            self.headers = headers or {}

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if method == "GET":
            return FakeResponse(
                [{"id": "1", "company_name": "Acme"}],
                {"content-range": "0-0/1"},
            )
        if method == "POST":
            return FakeResponse([{"id": "2", **kwargs["json"]}])
        if method == "PATCH":
            return FakeResponse([{"id": "2", **kwargs["json"]}])
        if method == "DELETE":
            return FakeResponse([{"id": "2"}])
        raise AssertionError(method)

    monkeypatch.setattr(
        "scraper.api.repositories.startup_repository.httpx.request",
        fake_request,
    )
    repository = SupabaseStartupRepository("startup_ai_radar_catalog")

    rows, total = repository.list(offset=0, limit=20)
    created = repository.create(
        {"candidate_id": "candidate-2", "company_name": "Beta"}
    )
    updated = repository.update("2", {"company_name": "Beta AI"})
    deleted = repository.delete("2")

    assert total == 1
    assert rows[0]["company_name"] == "Acme"
    assert created["id"] == "2"
    assert updated and updated["company_name"] == "Beta AI"
    assert deleted is True
    assert [call[0] for call in calls] == [
        "GET",
        "POST",
        "PATCH",
        "DELETE",
    ]


def test_supabase_repository_rest_dashboard_summary_counts(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")
    calls = []

    class FakeResponse:
        def __init__(self, payload, headers=None):
            self._payload = payload
            self.headers = headers or {}

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        params = kwargs["params"]
        if params["select"] == "id":
            return FakeResponse([{"id": "1"}], {"content-range": "0-0/3"})
        return FakeResponse(
            [
                {
                    "validation_status": "APPROVED",
                    "enrichment_status": "enriched",
                    "ai_dependency_level": "AI_ENABLED",
                    "nvidia_recommendation": {"ok": True},
                    "created_at": "2026-06-29T12:00:00Z",
                },
                {
                    "validation_status": "REVIEW",
                    "enrichment_status": "needs_review",
                    "ai_dependency_level": "AI_ENABLED",
                    "nvidia_recommendation": None,
                    "created_at": "2026-06-30T12:00:00Z",
                },
                {
                    "validation_status": "APPROVED",
                    "enrichment_status": "enriched",
                    "ai_dependency_level": "AI_NATIVE",
                    "nvidia_recommendation": {"ok": True},
                    "created_at": "2026-06-25T12:00:00Z",
                },
            ]
        )

    monkeypatch.setattr(
        "scraper.api.repositories.startup_repository.httpx.request",
        fake_request,
    )
    repository = SupabaseStartupRepository("startup_ai_radar_catalog")

    summary = repository.dashboard_summary_counts()

    assert summary["total_startups"] == 3
    assert summary["validation_statuses"] == {"APPROVED": 2, "REVIEW": 1}
    assert summary["enrichment_statuses"] == {
        "enriched": 2,
        "needs_review": 1,
    }
    assert summary["ai_classifications"] == {
        "AI_ENABLED": 2,
        "AI_NATIVE": 1,
    }
    assert summary["recommendations_count"] == 2
    assert summary["github_actions_registrations"] == [
        {"date": "2026-06-25", "count": 1},
        {"date": "2026-06-29", "count": 1},
    ]
    assert len(calls) == 2


def test_postgres_repository_adapts_dict_to_json():
    from psycopg2.extras import Json

    value = {"schema_version": "technology-intelligence/v1"}
    adapted = SupabaseStartupRepository._postgres_value(value)

    assert isinstance(adapted, Json)
    assert adapted.adapted == value
    assert SupabaseStartupRepository._postgres_value(["Python"]) == [
        "Python"
    ]
