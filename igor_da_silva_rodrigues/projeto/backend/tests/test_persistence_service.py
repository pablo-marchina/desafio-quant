from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.persistence.models import AIAssessment
from app.persistence.persistence_service import PipelinePersistence
from app.persistence.web_cache import SupabaseWebContentCache
from app.persistence.web_cache import web_usage_context


class FakeQuery:
    def __init__(self, database, table_name):
        self.database = database
        self.table_name = table_name
        self.operation = "select"
        self.payload = None
        self.filters = []
        self.limit_count = None
        self.conflict_fields = []

    def select(self, columns="*"):
        self.operation = "select"
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
        return self

    def upsert(self, payload, on_conflict=None):
        self.operation = "upsert"
        self.payload = payload
        self.conflict_fields = (on_conflict or "").split(",") if on_conflict else []
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def eq(self, field, value):
        self.filters.append(("eq", field, str(value)))
        return self

    def ilike(self, field, value):
        self.filters.append(("ilike", field, str(value)))
        return self

    def limit(self, count):
        self.limit_count = count
        return self

    def order(self, field, desc=False):
        return self

    def execute(self):
        rows = self.database.rows.setdefault(self.table_name, [])
        if self.operation == "select":
            selected = [row.copy() for row in rows if self._matches(row)]
            if self.limit_count is not None:
                selected = selected[: self.limit_count]
            return SimpleNamespace(data=selected)
        if self.operation == "insert":
            inserted = self._insert_many(rows, self.payload)
            return SimpleNamespace(data=inserted)
        if self.operation == "upsert":
            payloads = self.payload if isinstance(self.payload, list) else [self.payload]
            output = []
            for payload in payloads:
                existing = next(
                    (
                        row
                        for row in rows
                        if self.conflict_fields
                        and all(str(row.get(field)) == str(payload.get(field)) for field in self.conflict_fields)
                    ),
                    None,
                )
                if existing:
                    existing.update(payload)
                    output.append(existing.copy())
                else:
                    output.extend(self._insert_many(rows, payload))
            return SimpleNamespace(data=output)
        if self.operation == "update":
            updated = []
            for row in rows:
                if self._matches(row):
                    row.update(self.payload)
                    updated.append(row.copy())
            return SimpleNamespace(data=updated)
        raise AssertionError(self.operation)

    def _insert_many(self, rows, payload):
        payloads = payload if isinstance(payload, list) else [payload]
        inserted = []
        for item in payloads:
            row = {**item, "id": item.get("id") or str(uuid4())}
            rows.append(row)
            inserted.append(row.copy())
        return inserted

    def _matches(self, row):
        for operator, field, value in self.filters:
            current = str(row.get(field, ""))
            if operator == "eq" and current != value:
                return False
            if operator == "ilike" and current.lower() != value.lower():
                return False
        return True


class FakeDatabase:
    def __init__(self):
        self.rows = {}

    def table(self, name):
        return FakeQuery(self, name)


class FakeBucket:
    def __init__(self, files):
        self.files = files

    def upload(self, path, file, file_options=None):
        self.files[path] = {"file": file, "options": file_options}
        return {"path": path}


class FakeStorage:
    def __init__(self):
        self.files = {}

    def from_(self, bucket):
        return FakeBucket(self.files.setdefault(bucket, {}))


class FakeSupabase:
    def __init__(self):
        self.database = FakeDatabase()
        self.storage = FakeStorage()
        self.requested_schema = None

    def schema(self, name):
        self.requested_schema = name
        return self.database


def test_persistence_service_saves_complete_normalized_run():
    client = FakeSupabase()
    service = PipelinePersistence(client=client)

    startup_id = service.save_startup(
        {"nome": "Clara Pagamentos", "site_oficial": "https://clara.com.br"}
    )
    duplicate_id = service.save_startup(
        {"nome": "Clara Pagamentos", "site_oficial": "https://clara.com.br"}
    )
    run_id = service.create_pipeline_run(startup_id)

    assert startup_id == duplicate_id
    assert client.requested_schema == "nvidia_inception"

    assert service.save_queries(
        run_id,
        [{"consulta": "Clara IA", "camada": 3, "objetivo": "IA", "resultados_count": 2}],
    ) == 1
    assert service.save_evidences(
        run_id,
        [
            {
                "url": "https://clara.com.br/ia",
                "tipo_fonte": "oficial",
                "credibilidade": 0.7,
                "trecho": "Clara usa machine learning.",
                "score_confianca": 0.91,
                "classificacao": "alta",
                "contem_ia": True,
            }
        ],
    ) == 1
    assessment_id = service.save_assessment(
        run_id,
        {
            "classificacao": "AI-enabled",
            "nivel_maturidade": 3,
            "confianca_classificacao": 0.8,
            "tecnologias_utilizadas": {"frameworks": []},
            "necessidades": ["latencia"],
            "justificativa": "Evidências qualificadas.",
            "evidencias_usadas": ["https://clara.com.br/ia"],
        },
    )
    inception_fit_id = service.save_inception_fit(
        run_id,
        {
            "startup": "Clara Pagamentos",
            "eligibility_status": "unknown",
            "eligibility_justification": "Dados insuficientes.",
            "startup_stage": "unknown",
            "stage_justification": "Rodada nao informada.",
            "needs": [],
            "benefit_matches": [],
            "open_questions": ["Confirmar elegibilidade."],
        },
    )
    recommendation_id = service.save_recommendation(
        run_id,
        {
            "startup": "Clara Pagamentos",
            "recomendacoes": [{"tecnologia": "Triton", "fit_score": 0.86}],
        },
        [
            {
                "tecnologia": "Triton",
                "trecho_doc": "Triton oferece inferência escalável.",
                "url_doc": "https://docs.nvidia.com/triton",
            }
        ],
    )
    refinement_id = service.save_refinement(
        run_id,
        {
            "startup": "Clara Pagamentos",
            "recomendacao_refinada": {"fit_score": 0.84, "tecnologias_priorizadas": []},
        },
    )
    impact_id = service.save_impact_estimate(
        run_id,
        {
            "startup": "Clara Pagamentos",
            "indice_impacto_agregado": 76,
            "estimativas_impacto": [],
        },
    )
    briefing_id = service.save_briefing(
        run_id,
        {"startup": "Clara Pagamentos", "markdown": "# Briefing NVIDIA Inception"},
    )
    trace_path = service.upload_trace(run_id, {"search_planner": {"status": "completo"}})
    service.update_stage(run_id, "completed", "completed", {"errors": []})

    assert isinstance(assessment_id, UUID)
    assert isinstance(inception_fit_id, UUID)
    assert isinstance(recommendation_id, UUID)
    assert isinstance(refinement_id, UUID)
    assert isinstance(impact_id, UUID)
    assert isinstance(briefing_id, UUID)
    assert trace_path == f"{run_id}.json"
    assert trace_path in client.storage.files["pipeline-traces"]
    assert client.database.rows["pipeline_runs"][0]["status"] == "completed"
    assert client.database.rows["pipeline_runs"][0]["duration_ms"] >= 0
    assert len(client.database.rows["recommendation_citations"]) == 1
    assert client.database.rows["recommendation_refinements"][0]["fit_score"] == 0.84
    assert client.database.rows["impact_estimates"][0]["aggregate_index"] == 76
    assert client.database.rows["executive_briefings"][0]["markdown"].startswith("# Briefing")
    assert client.database.rows["inception_fit_assessments"][0]["eligibility_status"] == "unknown"


def test_non_ai_assessment_requires_maturity_zero():
    with pytest.raises(ValidationError):
        AIAssessment(
            pipeline_run_id=uuid4(),
            classificacao="Non-AI",
            nivel_maturidade=2,
            confianca_classificacao=0.8,
            justificativa="Sem evidências.",
        )


def test_web_content_cache_persists_content_and_usage():
    client = FakeSupabase()
    persistence = PipelinePersistence(client=client)
    cache = SupabaseWebContentCache(persistence, ttl_seconds=60)
    url = "https://example.com/tecnologia"
    content = {"url": url, "conteudo_markdown": "# Tecnologia"}

    assert cache.get(url) is None
    cache.set(url, content)
    with web_usage_context("00000000-0000-0000-0000-000000000001", "Clara"):
        cache.record_usage(url, cache_hit=False, success=True, estimated_cost_usd=0.01)

    assert cache.get(url) == content
    usage = client.database.rows["external_api_usage"][0]
    assert usage["provider"] == "firecrawl"
    assert usage["source_domain"] == "example.com"
    assert usage["estimated_cost_usd"] == 0.01
    assert usage["batch_run_id"] == "00000000-0000-0000-0000-000000000001"
    assert usage["startup_name"] == "Clara"


def test_migration_contains_security_and_storage_requirements():
    from pathlib import Path

    sql = (Path(__file__).resolve().parents[1] / "app/persistence/migration.sql").read_text(
        encoding="utf-8"
    )

    assert "create schema if not exists nvidia_inception" in sql.lower()
    assert sql.lower().count("enable row level security") == 19
    assert "web_content_cache" in sql
    assert "external_api_usage" in sql
    assert "reserve_external_api_usage" in sql
    assert "consume_api_rate_limit" in sql
    assert "revoked_auth_tokens" in sql
    assert "to service_role" in sql
    assert "pipeline-traces" in sql
    assert "startups_nome_lower_uidx" in sql
    assert "pgrst.db_schemas" in sql
    assert "notify pgrst, 'reload schema'" in sql
