from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from src.orchestration.graph import NodeExecutionError, build_workflow_graph, session_var
from src.orchestration.state import ProductWorkflowState, WorkflowStatus
from src.repositories.workflow import WorkflowRepository

try:
    from langgraph.types import Command

    _LANGGRAPH_COMMAND_AVAILABLE = True
except ImportError:
    Command = None  # type: ignore[assignment]
    _LANGGRAPH_COMMAND_AVAILABLE = False

_HAS_LANGGRAPH: bool | None = None


def _has_langgraph() -> bool:
    global _HAS_LANGGRAPH
    if _HAS_LANGGRAPH is not None:
        return _HAS_LANGGRAPH
    try:
        import langgraph  # noqa: F401

        _HAS_LANGGRAPH = True
    except ImportError:
        _HAS_LANGGRAPH = False
    return _HAS_LANGGRAPH


_POSTGRES_CHECKPOINTER: Any | None = None
_POSTGRES_CHECKPOINTER_ERROR: str | None = None
_CHECKPOINTER_CACHE: dict[str, Any] = {}


def _normalize_postgres_connection_url(raw_url: str) -> str:
    """Return a psycopg-compatible PostgreSQL URL from a SQLAlchemy URL."""
    value = raw_url.strip()
    if not value:
        return ""
    url = make_url(value)
    if not url.get_backend_name().startswith("postgresql"):
        raise ValueError("LangGraph checkpointer URL must use PostgreSQL")
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


def _get_postgres_checkpointer_url() -> str:
    explicit = os.environ.get("LANGGRAPH_POSTGRES_URL", "").strip()
    if explicit:
        return _normalize_postgres_connection_url(explicit)

    from src.database.session import get_product_db_url

    return _normalize_postgres_connection_url(get_product_db_url())


def _build_postgres_checkpointer() -> Any | None:
    global _POSTGRES_CHECKPOINTER, _POSTGRES_CHECKPOINTER_ERROR
    if _POSTGRES_CHECKPOINTER is not None:
        return _POSTGRES_CHECKPOINTER
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
        import psycopg
        from psycopg.rows import dict_row

        url = _get_postgres_checkpointer_url()
        conn = psycopg.connect(url, autocommit=True, prepare_threshold=0, row_factory=dict_row)
        saver = PostgresSaver(conn)
        saver.setup()
        _POSTGRES_CHECKPOINTER = saver
        _POSTGRES_CHECKPOINTER_ERROR = None
        return saver
    except Exception as exc:
        _POSTGRES_CHECKPOINTER_ERROR = f"{type(exc).__name__}: {exc}"
        return None


def _build_checkpointer() -> Any | None:
    pg = _build_postgres_checkpointer()
    if pg is not None:
        return pg
    if _is_explicit_product_mode():
        return None
    try:
        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()
    except ImportError:
        return None


def _is_explicit_product_mode() -> bool:
    return os.environ.get("APP_MODE", "").casefold() == "product"


def _is_postgres_checkpointer(checkpointer: Any | None) -> bool:
    if checkpointer is None:
        return False
    cls = checkpointer.__class__
    return cls.__name__ == "PostgresSaver" or "postgres" in cls.__module__.casefold()


def _cache_checkpointer(thread_id: str, checkpointer: Any) -> None:
    _CHECKPOINTER_CACHE[thread_id] = checkpointer


def _get_cached_checkpointer(thread_id: str) -> Any | None:
    return _CHECKPOINTER_CACHE.get(thread_id)


def reset_checkpointer_runtime() -> None:
    """Clear cached checkpointers for deterministic tests and runtime reloads."""
    global _POSTGRES_CHECKPOINTER, _POSTGRES_CHECKPOINTER_ERROR
    _POSTGRES_CHECKPOINTER = None
    _POSTGRES_CHECKPOINTER_ERROR = None
    _CHECKPOINTER_CACHE.clear()


class WorkflowRunner:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = WorkflowRepository(session)

    def _dump_state(self, state: ProductWorkflowState) -> dict[str, Any]:
        session_value = state.metadata_json.pop("_session", None)
        try:
            return state.model_dump(mode="json")
        finally:
            if session_value is not None:
                state.metadata_json["_session"] = session_value

    def _ensure_analysis_run(self, state: ProductWorkflowState) -> str | None:
        if state.analysis_run_id:
            return state.analysis_run_id
        if not state.startup_id:
            return None
        from src.repositories.product import ProductRepository

        repo = ProductRepository(self.session)
        run = repo.create_analysis_run(
            startup_id=state.startup_id,
            input_snapshot={},
            pipeline_version="orchestration_graph+v1",
            corpus_version=None,
            config_snapshot={},
        )
        self.session.flush()
        return run.id

    def _attach_analysis_run(self, state: ProductWorkflowState, analysis_run_id: str) -> None:
        """Persist the workflow-to-analysis link used by APIs and the frontend."""
        workflow = self.repo.get_workflow_run(state.workflow_id)
        if workflow is None:
            raise LookupError(f"WorkflowRun not found: {state.workflow_id}")
        workflow.analysis_run_id = analysis_run_id
        if state.startup_id and workflow.startup_id is None:
            workflow.startup_id = state.startup_id
        self.session.flush()

    def _sync_analysis_run(
        self,
        state: ProductWorkflowState,
        *,
        status: str,
        error_message: str | None = None,
        degraded_reason: str | None = None,
    ) -> None:
        """Keep the persisted AnalysisRun aligned with the canonical workflow."""
        if not state.analysis_run_id:
            return
        from src.orchestration.result_adapter import workflow_state_to_output_snapshot
        from src.repositories.product import ProductRepository

        product_repo = ProductRepository(self.session)
        run = product_repo.get_analysis_run(state.analysis_run_id)
        if run is None:
            return
        terminal = status in {
            WorkflowStatus.COMPLETED,
            WorkflowStatus.DEGRADED,
            WorkflowStatus.FAILED,
            WorkflowStatus.CANCELLED,
        }
        product_repo.update_analysis_run_status(
            state.analysis_run_id,
            status=status,
            started_at=run.started_at or datetime.now(UTC),
            completed_at=datetime.now(UTC) if terminal else None,
            error_message=error_message,
            degraded_reason=degraded_reason,
            output_snapshot=workflow_state_to_output_snapshot(state),
        )
        self.session.flush()

    def _fail_state(self, state: ProductWorkflowState, error_message: str, *, node_name: str = "") -> None:
        state.status = WorkflowStatus.FAILED
        state.error_message = error_message
        if node_name:
            state.current_node = node_name
            if node_name not in state.failed_nodes:
                state.failed_nodes.append(node_name)
        self.repo.fail_workflow(
            state.workflow_id,
            error_message=error_message,
            state_json=self._dump_state(state),
        )
        self._sync_analysis_run(state, status=WorkflowStatus.FAILED, error_message=error_message)

    def run_workflow(self, state: ProductWorkflowState) -> ProductWorkflowState:
        analysis_run_id = self._ensure_analysis_run(state)
        if analysis_run_id:
            state.analysis_run_id = analysis_run_id
            self._attach_analysis_run(state, analysis_run_id)
            self._sync_analysis_run(state, status=WorkflowStatus.RUNNING)

        checkpointer = _build_checkpointer()
        if _is_explicit_product_mode() and not _is_postgres_checkpointer(checkpointer):
            detail = f" Root cause: {_POSTGRES_CHECKPOINTER_ERROR}" if _POSTGRES_CHECKPOINTER_ERROR else ""
            self._fail_state(
                state,
                "APP_MODE=product requires a persistent LangGraph Postgres checkpointer." + detail,
                node_name="preflight_configuration_check",
            )
            return state

        try:
            from src.orchestration import graph as graph_module

            readiness = graph_module.ProductReadinessService().get_product_readiness()
            if getattr(readiness, "ready", True) is False:
                messages = [str(message) for message in (getattr(readiness, "user_messages", []) or [])]
                self._fail_state(
                    state,
                    "; ".join(messages) or "Product readiness preflight failed",
                    node_name="preflight_configuration_check",
                )
                return state
        except Exception:
            pass

        graph = build_workflow_graph(checkpointer=checkpointer)
        if graph is None:
            self._fail_state(
                state,
                "LangGraph is not available. It is required to build the workflow graph.",
                node_name="preflight_configuration_check",
            )
            return state

        return self._run_with_langgraph(state, graph, checkpointer=checkpointer)

    def _run_with_langgraph(
        self,
        state: ProductWorkflowState,
        graph: Any,
        *,
        checkpointer: Any | None = None,
    ) -> ProductWorkflowState:
        state.status = WorkflowStatus.RUNNING
        self.repo.update_workflow_status(
            state.workflow_id,
            status=WorkflowStatus.RUNNING,
            current_node="",
            state_json=self._dump_state(state),
        )
        # Establish a durable workflow/analysis boundary before node execution.
        # If a later node flush fails, rolling back must not delete the workflow
        # record that is needed to persist the concrete failure for the API/UI.
        self.session.commit()

        thread_id = state.analysis_run_id or state.workflow_id
        config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}
        if checkpointer is not None:
            _cache_checkpointer(thread_id, checkpointer)

        input_data: dict[str, Any] = state.model_dump()
        token = session_var.set(self.session)
        try:
            result = graph.invoke(input_data, config)
        except NodeExecutionError as exc:
            # A failed flush leaves SQLAlchemy in PendingRollbackError state.
            # Restore the session before writing the durable workflow failure.
            self.session.rollback()
            self._fail_state(state, exc.error_message or f"Node failed: {exc.node_name}", node_name=exc.node_name)
            return state
        except Exception as exc:
            self.session.rollback()
            node_name = state.current_node or "workflow_execution"
            self._fail_state(
                state,
                f"Workflow execution failed: {type(exc).__name__}: {exc}",
                node_name=node_name,
            )
            return state
        finally:
            session_var.reset(token)

        if isinstance(result, dict) and "__interrupt__" in result:
            return self._handle_interrupt(state, result, thread_id)

        self._finalize_workflow(state, result)
        return state

    def _handle_interrupt(
        self,
        state: ProductWorkflowState,
        result: dict[str, Any],
        thread_id: str,
    ) -> ProductWorkflowState:
        state.metadata_json["_langgraph_thread_id"] = thread_id
        interrupts = result.get("__interrupt__", [])
        if interrupts and hasattr(interrupts[0], "value"):
            payload = interrupts[0].value
            state.review_payload = payload if isinstance(payload, dict) else {"value": payload}
        state.review_required = True
        state.status = WorkflowStatus.AWAITING_REVIEW
        state.current_node = "needs_review"

        self.repo.update_workflow_status(
            state.workflow_id,
            status=WorkflowStatus.AWAITING_REVIEW,
            current_node="needs_review",
            state_json=self._dump_state(state),
        )
        self._sync_analysis_run(state, status=WorkflowStatus.AWAITING_REVIEW)
        return state

    def _finalize_workflow(self, state: ProductWorkflowState, result: Any) -> None:
        if isinstance(result, ProductWorkflowState):
            state_data = result.model_dump()
        elif isinstance(result, dict):
            state_data = result
        else:
            state_data = {}

        for key, value in state_data.items():
            if hasattr(state, key):
                setattr(state, key, value)

        if state.degraded_nodes:
            state.status = WorkflowStatus.DEGRADED
            reason = f"Degraded nodes: {', '.join(dict.fromkeys(state.degraded_nodes))}"
            self.repo.degrade_workflow(
                state.workflow_id,
                degraded_reason=reason,
                state_json=self._dump_state(state),
            )
            self._sync_analysis_run(state, status=WorkflowStatus.DEGRADED, degraded_reason=reason)
        else:
            state.status = WorkflowStatus.COMPLETED
            self.repo.complete_workflow(state.workflow_id, state_json=self._dump_state(state))
            self._sync_analysis_run(state, status=WorkflowStatus.COMPLETED)

    def resume_workflow(
        self,
        state: ProductWorkflowState,
        *,
        decision: str,
        notes: str = "",
        reviewed_by: str = "",
    ) -> ProductWorkflowState:
        thread_id = state.metadata_json.get("_langgraph_thread_id")
        if not thread_id:
            raise RuntimeError(f"No checkpoint thread_id found for workflow {state.workflow_id}")

        checkpointer = _get_cached_checkpointer(thread_id)
        if checkpointer is None:
            checkpointer = _build_checkpointer()
            if checkpointer is not None:
                _cache_checkpointer(thread_id, checkpointer)
        if checkpointer is None:
            detail = f" Root cause: {_POSTGRES_CHECKPOINTER_ERROR}" if _POSTGRES_CHECKPOINTER_ERROR else ""
            raise RuntimeError(
                f"Cannot resume workflow {state.workflow_id}: no persistent checkpointer for thread_id {thread_id}." + detail
            )
        if _is_explicit_product_mode() and not _is_postgres_checkpointer(checkpointer):
            raise RuntimeError("APP_MODE=product requires a persistent LangGraph Postgres checkpointer for resume.")

        graph = build_workflow_graph(checkpointer=checkpointer)
        if graph is None:
            raise RuntimeError("Cannot resume: LangGraph workflow graph is not available")
        if not _LANGGRAPH_COMMAND_AVAILABLE:
            raise RuntimeError("langgraph.types.Command is not available")

        config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}
        state.status = WorkflowStatus.RUNNING
        self.repo.update_workflow_status(
            state.workflow_id,
            status=WorkflowStatus.RUNNING,
            current_node="needs_review",
            state_json=self._dump_state(state),
        )
        self._sync_analysis_run(state, status=WorkflowStatus.RUNNING)
        self.session.commit()

        token = session_var.set(self.session)
        try:
            result = graph.invoke(
                Command(
                    resume=decision,
                    update={
                        "review_decision": decision,
                        "review_notes": notes,
                        "reviewed_by": reviewed_by,
                    },
                ),
                config,
            )
        except NodeExecutionError as exc:
            self.session.rollback()
            self._fail_state(state, exc.error_message or f"Node failed: {exc.node_name}", node_name=exc.node_name)
            return state
        except Exception as exc:
            self.session.rollback()
            self._fail_state(
                state,
                f"Workflow resume failed: {type(exc).__name__}: {exc}",
                node_name=state.current_node or "needs_review",
            )
            return state
        finally:
            session_var.reset(token)

        if (
            decision == "approve"
            and isinstance(result, dict)
            and result.get("review_decision") == "approve"
            and "__interrupt__" in result
        ):
            result = dict(result)
            result.pop("__interrupt__", None)
            result["status"] = WorkflowStatus.COMPLETED
            result["review_required"] = False

        if isinstance(result, dict) and "__interrupt__" in result:
            return self._handle_interrupt(state, result, thread_id)

        self._finalize_workflow(state, result)
        return state


def create_runner(session: Session) -> WorkflowRunner:
    return WorkflowRunner(session)
