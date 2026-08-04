from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

import src.orchestration.node_impl  # noqa: F401 - populate WORKFLOW_NODES
from src.database.session import configure_product_database, reset_product_database_runtime
from src.orchestration.nodes import WORKFLOW_NODES
from src.orchestration.runner import WorkflowRunner, _has_langgraph
from src.orchestration.state import ProductWorkflowState, WorkflowStatus
from src.repositories.workflow import WorkflowRepository


@pytest.fixture
def session(tmp_path: Path):
    runtime = configure_product_database(f"sqlite:///{(tmp_path / 'runner.db').as_posix()}")
    sess = runtime.session_factory()
    yield sess
    sess.close()
    reset_product_database_runtime()


@pytest.fixture
def runner(session) -> WorkflowRunner:
    return WorkflowRunner(session)


def test_workflow_nodes_are_registered() -> None:
    expected = {
        "load_startup_or_candidate",
        "plan_search",
        "collect_sources",
        "extract_profile",
        "validate_evidence",
        "score_startup_probabilistic",
        "diagnose_gaps",
        "retrieve_nvidia_context",
        "enhance_contexts_with_techniques",
        "rank_with_expected_utility",
        "map_nvidia_technologies",
        "rank_recommendations",
        "generate_brief",
        "run_quality_gates",
        "generate_claims",
        "match_activation_playbooks",
        "generate_activation_dossier",
        "run_product_quality",
        "summarize_readiness",
        "needs_review",
        "apply_feedback_weights",
        "write_decision_ledger",
    }
    node_names = {n.name for n in WORKFLOW_NODES}
    assert node_names == expected, f"Missing: {expected - node_names}, Extra: {node_names - expected}"
    assert len(WORKFLOW_NODES) == 22


def test_workflow_nodes_have_required_fields() -> None:
    for node in WORKFLOW_NODES:
        assert node.name
        assert node.description
        assert node.critical is not None


def test_runner_handles_missing_langgraph(runner: WorkflowRunner, session) -> None:
    from unittest.mock import patch

    with (
        patch("src.orchestration.graph.ProductReadinessService") as mock_service,
        patch("src.orchestration.runner.build_workflow_graph", return_value=None),
    ):
        mock_service.return_value.get_product_readiness.return_value.ready = True
        repo = WorkflowRepository(session)
        run = repo.create_workflow_run()
        session.commit()
        state = ProductWorkflowState(
            workflow_id=run.id,
            current_node="load_startup_or_candidate",
        )
        result_state = runner.run_workflow(state)
    assert result_state.workflow_id == run.id
    assert len(result_state.completed_nodes) == 0
    assert result_state.error_message is not None
    assert "LangGraph is not available" in result_state.error_message


def test_runner_has_langgraph_detection() -> None:
    result = _has_langgraph()
    assert isinstance(result, bool)



def test_runner_preflight_block_fails_workflow(runner: WorkflowRunner, session) -> None:
    from unittest.mock import patch

    with (
        patch("src.orchestration.graph.ProductReadinessService") as mock_service,
    ):
        report = MagicMock()
        report.ready = False
        report.user_messages = ["Database URL is not configured"]
        report.blocking_missing_config = []
        mock_service.return_value.get_product_readiness.return_value = report

        repo = WorkflowRepository(session)
        run = repo.create_workflow_run()
        session.commit()
        state = ProductWorkflowState(workflow_id=run.id)
        result_state = runner.run_workflow(state)

    assert result_state.workflow_id == run.id
    assert result_state.failed_nodes == ["preflight_configuration_check"]
    assert result_state.current_node == "preflight_configuration_check"
    assert result_state.completed_nodes == []
    assert result_state.error_message is not None
    assert "Database URL is not configured" in result_state.error_message


def test_runner_executes_with_session(runner: WorkflowRunner, session) -> None:
    repo = WorkflowRepository(session)
    run = repo.create_workflow_run(startup_id="s-1")
    session.commit()
    state = ProductWorkflowState(
        workflow_id=run.id,
        startup_id="s-1",
        current_node="load_startup_or_candidate",
    )
    result = runner.run_workflow(state)
    assert result is not None
    assert isinstance(result, ProductWorkflowState)


# ── make_workflow_persister ──────────────────────────────────────────────────────


def test_make_workflow_persister_updates_status(session) -> None:
    from src.database.models import AnalysisRun
    from src.repositories.product import ProductRepository
    from src.services.product.workflow_persister import make_workflow_persister

    repo = ProductRepository(session)
    run = repo.create_analysis_run(
        startup_id="s-persist",
        input_snapshot={},
        pipeline_version="test",
        corpus_version=None,
        config_snapshot={},
    )
    session.flush()

    persister = make_workflow_persister(session)
    persister(
        run.id,
        status="brief_generated",
        output_snapshot={"brief": "hello"},
    )

    session.expire_all()
    updated = session.get(AnalysisRun, run.id)
    assert updated is not None
    assert updated.status == "brief_generated"
    assert updated.output_snapshot_json == {"brief": "hello"}
    assert updated.completed_at is not None


# ── _ensure_analysis_run ────────────────────────────────────────────────────────


def test_ensure_analysis_run_creates_with_startup_id(runner: WorkflowRunner, session) -> None:
    from src.database.models import AnalysisRun

    state = ProductWorkflowState(
        workflow_id="w-ensure-1",
        startup_id="s-ensure",
    )
    analysis_run_id = runner._ensure_analysis_run(state)

    assert analysis_run_id is not None
    run = session.get(AnalysisRun, analysis_run_id)
    assert run is not None
    assert run.startup_id == "s-ensure"
    assert run.pipeline_version == "orchestration_graph+v1"


def test_ensure_analysis_run_reuses_existing(runner: WorkflowRunner, session) -> None:
    from src.repositories.product import ProductRepository

    repo = ProductRepository(session)
    existing = repo.create_analysis_run(
        startup_id="s-reuse",
        input_snapshot={},
        pipeline_version="v1",
        corpus_version=None,
        config_snapshot={},
    )
    session.flush()

    state = ProductWorkflowState(
        workflow_id="w-reuse",
        startup_id="s-reuse",
        analysis_run_id=existing.id,
    )
    result = runner._ensure_analysis_run(state)

    assert result == existing.id


def test_ensure_analysis_run_returns_none_without_startup(runner: WorkflowRunner, session) -> None:
    state = ProductWorkflowState(workflow_id="w-no-startup")
    result = runner._ensure_analysis_run(state)
    assert result is None


# ── run_workflow + analysis_run_id ──────────────────────────────────────────────


def test_run_workflow_with_graph_sets_analysis_run_id(runner: WorkflowRunner, session) -> None:
    from unittest.mock import MagicMock, patch

    from src.database.models import AnalysisRun

    repo = WorkflowRepository(session)
    run = repo.create_workflow_run(startup_id="s-graph")
    session.commit()

    state = ProductWorkflowState(
        workflow_id=run.id,
        startup_id="s-graph",
    )

    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {
        "completed_nodes": ["plan_search", "finish"],
    }

    with patch("src.orchestration.runner.build_workflow_graph", return_value=mock_graph):
        result_state = runner.run_workflow(state)

    analysis_run = session.query(AnalysisRun).filter_by(startup_id="s-graph").first()
    assert analysis_run is not None
    assert analysis_run.pipeline_version == "orchestration_graph+v1"
    assert result_state.analysis_run_id == analysis_run.id


def test_run_workflow_without_startup_id_does_not_create_analysis_run(runner: WorkflowRunner, session) -> None:
    from unittest.mock import MagicMock, patch

    from src.database.models import AnalysisRun

    repo = WorkflowRepository(session)
    run = repo.create_workflow_run()
    session.commit()

    state = ProductWorkflowState(
        workflow_id=run.id,
    )

    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {
        "completed_nodes": [],
    }

    count_before = session.query(AnalysisRun).count()

    with patch("src.orchestration.runner.build_workflow_graph", return_value=mock_graph):
        runner.run_workflow(state)

    count_after = session.query(AnalysisRun).count()
    assert count_after == count_before


# ── E2E interrupt / resume ────────────────────────────────────────────────────────


class TestRunnerInterruptResume:
    """Full E2E: run_workflow → interrupt at needs_review → cache checkpointer → resume_workflow → complete."""

    @staticmethod
    def _patched_build_graph(*, checkpointer=None):
        from unittest.mock import MagicMock

        graph = MagicMock(spec=["invoke"])

        def invoke(input_data, config):
            return {
                "completed_nodes": [
                    "plan_search",
                    "collect_sources",
                    "load_startup_or_candidate",
                    "collect_or_load_evidence",
                    "validate_evidence",
                    "diagnose_gaps",
                    "retrieve_nvidia_context",
                    "map_nvidia_technologies",
                    "generate_claims",
                    "match_activation_playbooks",
                    "generate_activation_dossier",
                    "run_product_quality",
                    "summarize_readiness",
                ],
                "status": "completed",
            }

        graph.invoke = invoke
        return graph

    @staticmethod
    def _patched_interrupt_graph(*, checkpointer=None):
        from unittest.mock import MagicMock

        graph = MagicMock(spec=["invoke"])

        def invoke(input_data, config):
            return {
                "__interrupt__": [MagicMock(value={"needs_review": True})],
                "completed_nodes": ["run_product_quality"],
                "status": "needs_human_review",
                "review_required": True,
                "review_payload": {"needs_review": True},
            }

        graph.invoke = invoke
        return graph

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _needs_review_quality_result() -> dict:
        return {
            "status": "needs_human_review",
            "quality": {
                "status": "needs_review",
                "failed_checks": [],
                "warning_checks": ["evidence_items_count == 0"],
                "metrics": {},
                "thresholds": {},
            },
            "review_required": True,
            "executed_nodes": ["run_quality_gates"],
        }

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_interrupt_pauses_workflow(self, runner: WorkflowRunner, session) -> None:
        from unittest.mock import patch

        from src.orchestration.runner import _CHECKPOINTER_CACHE, _get_cached_checkpointer

        _CHECKPOINTER_CACHE.clear()

        repo = WorkflowRepository(session)
        run = repo.create_workflow_run(startup_id="s-e2e-pause")
        session.commit()

        state = ProductWorkflowState(workflow_id=run.id, startup_id="s-e2e-pause")

        ready_report = MagicMock()
        ready_report.ready = True

        with (
            patch(
                "src.services.product.readiness_service.ProductReadinessService.get_product_readiness",
                return_value=ready_report,
            ),
            patch("src.orchestration.runner._build_checkpointer", return_value=object()),
            patch("src.orchestration.runner.build_workflow_graph", self._patched_interrupt_graph),
        ):
            result_state = runner.run_workflow(state)

        assert (
            result_state.status == WorkflowStatus.AWAITING_REVIEW
        ), f"Expected AWAITING_REVIEW, got {result_state.status}"
        # _langgraph_thread_id is stored in the DB state_json, not on the returned state
        session.expire_all()
        wf_run = repo.get_workflow_run(run.id)
        assert wf_run is not None
        sj = wf_run.state_json or {}
        thread_id = sj.get("metadata_json", {}).get("_langgraph_thread_id")
        assert thread_id is not None, "No _langgraph_thread_id in DB state_json metadata"
        assert result_state.analysis_run_id is not None, "No analysis_run_id"

        cached = _get_cached_checkpointer(thread_id)
        assert cached is not None, "No cached checkpointer for thread_id"

    def test_resume_approve_completes_workflow(self, runner: WorkflowRunner, session) -> None:
        from unittest.mock import MagicMock, patch

        from src.orchestration.runner import _CHECKPOINTER_CACHE

        _CHECKPOINTER_CACHE.clear()

        repo = WorkflowRepository(session)
        run = repo.create_workflow_run(startup_id="s-e2e-resume")
        session.commit()

        state = ProductWorkflowState(workflow_id=run.id, startup_id="s-e2e-resume")
        ready_report = MagicMock()
        ready_report.ready = True

        with (
            patch(
                "src.services.product.readiness_service.ProductReadinessService.get_product_readiness",
                return_value=ready_report,
            ),
            patch("src.orchestration.runner._build_checkpointer", return_value=object()),
            patch("src.orchestration.runner.build_workflow_graph", self._patched_interrupt_graph),
        ):
            result_state = runner.run_workflow(state)

        # Reconstruct resume state from DB (same pattern as service.py submit_review)
        session.expire_all()
        wf_run = repo.get_workflow_run(run.id)
        assert wf_run is not None
        state_data: dict = dict(wf_run.state_json or {})
        state_data["workflow_id"] = wf_run.id
        state_data["startup_id"] = wf_run.startup_id
        state_data["current_node"] = wf_run.current_node
        resume_state = ProductWorkflowState(**state_data)

        class _Command:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        with (
            patch("src.orchestration.runner._LANGGRAPH_COMMAND_AVAILABLE", True),
            patch("src.orchestration.runner.Command", _Command),
            patch("src.orchestration.runner.build_workflow_graph", self._patched_build_graph),
        ):
            result2 = runner.resume_workflow(resume_state, decision="approve")

        assert result2.status in (
            "human_review_approved",
            "persistence_failed",
            "completed",
        ), f"Expected finished status, got {result2.status}"
        assert result2.analysis_run_id == result_state.analysis_run_id

        # DB must mark the workflow as completed
        session.expire_all()
        wf_run2 = repo.get_workflow_run(run.id)
        assert wf_run2 is not None
        assert wf_run2.status == "completed", f"DB status should be completed, got {wf_run2.status}"

    def test_resume_without_cached_checkpointer_raises(self, runner: WorkflowRunner, session) -> None:
        from unittest.mock import patch

        from src.orchestration.runner import _CHECKPOINTER_CACHE

        _CHECKPOINTER_CACHE.clear()

        repo = WorkflowRepository(session)
        run = repo.create_workflow_run(startup_id="s-e2e-no-cache")
        session.commit()

        state = ProductWorkflowState(
            workflow_id=run.id,
            startup_id="s-e2e-no-cache",
            metadata_json={
                "_langgraph_thread_id": "nonexistent-thread",
            },
        )
        with (
            patch("src.orchestration.runner._build_checkpointer", return_value=None),
            pytest.raises(RuntimeError, match="no cached or persistent checkpointer"),
        ):
            runner.resume_workflow(state, decision="approve")
