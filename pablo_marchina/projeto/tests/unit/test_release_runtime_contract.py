from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import yaml

from src.database.session import configure_product_database, reset_product_database_runtime
from src.orchestration.runner import WorkflowRunner, _normalize_postgres_connection_url
from src.orchestration.state import ProductWorkflowState
from src.repositories.product import ProductRepository
from src.repositories.workflow import WorkflowRepository


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_env_example() -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in (REPO_ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def test_local_product_ports_and_database_are_consistent() -> None:
    env = _read_env_example()
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8"))

    assert env["PRODUCT_DB_URL"] == "postgresql+psycopg://postgres:postgres@localhost:5432/startup_radar"
    assert env["LANGGRAPH_POSTGRES_URL"] == "postgresql://postgres:postgres@localhost:5432/startup_radar"
    assert env["VITE_API_BASE_URL"] == "http://localhost:8000"
    assert env["TRITON_RERANKER_URL"].startswith("http://localhost:8100/")
    assert compose["services"]["triton-reranker"]["ports"][0] == "8100:8000"
    assert compose["services"]["postgres"]["environment"]["POSTGRES_DB"] == "startup_radar"


def test_sqlalchemy_postgres_url_is_normalized_for_psycopg() -> None:
    raw = "postgresql+psycopg2://user:password@localhost:5432/database"
    assert _normalize_postgres_connection_url(raw) == "postgresql://user:password@localhost:5432/database"


def test_triton_model_contract_uses_explicit_tensor_shapes() -> None:
    config = (REPO_ROOT / "models" / "cross_encoder" / "config.pbtxt").read_text(encoding="utf-8")
    assert "max_batch_size: 0" in config
    assert 'name: "query"' in config and "dims: [1]" in config
    assert 'name: "documents"' in config and "dims: [-1, 1]" in config


def test_runner_persists_final_analysis_snapshot(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("APP_MODE", "test")
    database_url = f"sqlite:///{(tmp_path / 'release-contract.db').as_posix()}"
    configure_product_database(database_url)
    try:
        runtime = __import__("src.database.session", fromlist=["get_product_database"]).get_product_database()
        session = runtime.session_factory()
        product_repo = ProductRepository(session)
        workflow_repo = WorkflowRepository(session)
        startup = product_repo.create_startup(
            name="Release Contract AI",
            website="https://release-contract.example.com",
            country="Brazil",
            sector="AI",
            description="AI-native release contract startup",
            product_summary="Runs inference models in production",
            status="active",
            tags=["ai-native"],
        )
        session.flush()
        workflow = workflow_repo.create_workflow_run(startup_id=startup.id, graph_version="test")
        session.flush()

        class FakeGraph:
            def invoke(self, input_data, config):  # noqa: ANN001
                return {
                    "startup_profile": {"startup_name": "Release Contract AI"},
                    "scores": {"probabilistic_score": 0.82, "confidence": 0.78, "uncertainty": 0.12},
                    "evidence_weighted_scores": {"score": 0.82, "confidence": 0.78, "uncertainty": 0.12},
                    "ranked_recommendations": [
                        {"technology": "NVIDIA NIM", "expected_utility": 0.8, "confidence": 0.78}
                    ],
                    "completed_nodes": ["preflight_configuration_check", "finish"],
                    "degraded_nodes": [],
                    "failed_nodes": [],
                }

        state = ProductWorkflowState(workflow_id=workflow.id, startup_id=startup.id)
        with (
            patch("src.orchestration.runner._build_checkpointer", return_value=object()),
            patch("src.orchestration.runner.build_workflow_graph", return_value=FakeGraph()),
            patch(
                "src.services.product.readiness_service.ProductReadinessService.get_product_readiness",
                return_value=SimpleNamespace(ready=True, user_messages=[]),
            ),
        ):
            result = WorkflowRunner(session).run_workflow(state)

        session.commit()
        assert result.status == "completed"
        assert result.analysis_run_id
        analysis = product_repo.get_analysis_run(result.analysis_run_id)
        persisted_workflow = workflow_repo.get_workflow_run(workflow.id)
        assert analysis is not None
        assert persisted_workflow is not None
        assert persisted_workflow.analysis_run_id == result.analysis_run_id
        assert analysis.status == "completed"
        assert analysis.output_snapshot_json["workflow_id"] == workflow.id
        assert analysis.output_snapshot_json["startup_name"] == "Release Contract AI"
        assert analysis.output_snapshot_json["ranked_recommendations"][0]["technology"] == "NVIDIA NIM"
    finally:
        try:
            session.close()
        except UnboundLocalError:
            pass
        reset_product_database_runtime()
