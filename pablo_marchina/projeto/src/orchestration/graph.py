"""LangGraph StateGraph for the product workflow.

Each domain node is wrapped to adapt the NodeResult protocol to LangGraph's
state-update protocol. Per-node tracing (node_run records) is preserved.
"""

from __future__ import annotations

from contextvars import ContextVar
from time import perf_counter
from typing import Any
import os

from sqlalchemy.orm import Session

from src.observability.metrics import observe_node
from src.orchestration import node_impl  # noqa: F401 — triggers @_register decorators
from src.orchestration.nodes import WORKFLOW_NODES
from src.orchestration.state import NodeStatus, ProductWorkflowState
from src.repositories.workflow import WorkflowRepository
from src.services.product.readiness_service import ProductReadinessService

session_var: ContextVar[Session | None] = ContextVar("_session", default=None)

LANGGRAPH_AVAILABLE: bool
try:
    from langgraph.graph import StateGraph, START, END  # noqa: I001

    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False


class NodeExecutionError(Exception):
    """Raised when a LangGraph node execution fails."""

    def __init__(self, node_name: str, error_message: str) -> None:
        self.node_name = node_name
        self.error_message = error_message
        super().__init__(f"[{node_name}] {error_message}")


def _is_langgraph_interrupt(exc: BaseException) -> bool:
    """Return True for LangGraph control-flow interrupts.

    LangGraph uses an interrupt exception internally to pause execution for
    human-in-the-loop flows. Retry wrappers must never swallow or convert it
    into a node failure.
    """
    name = exc.__class__.__name__.casefold()
    module = exc.__class__.__module__.casefold()
    return "interrupt" in name or "graphinterrupt" in name or "langgraph" in module and "interrupt" in name


def _node_max_retries() -> int:
    raw = os.environ.get("WORKFLOW_NODE_MAX_RETRIES", "2")
    try:
        return max(0, min(5, int(raw)))
    except ValueError:
        return 2


def _preflight_configuration_check(state: ProductWorkflowState) -> dict[str, Any]:
    """Validate that the workflow can proceed with the given configuration.

    Checks:
      - ProductReadinessService (capabilities, env vars)
      - ConfigLoaderService (all YAML files load and validate)
    If not ready, raises NodeExecutionError with the blocking messages.
    """
    svc = ProductReadinessService()
    report = svc.get_product_readiness()

    blockers: list[str] = list(report.user_messages or [])

    from src.config.loader import ConfigLoaderService

    config_errors = ConfigLoaderService().validate_all()
    blockers.extend(config_errors)

    if blockers:
        msg = "; ".join(blockers)
        raise NodeExecutionError("preflight_configuration_check", msg)

    return {
        "status": "initialized",
        "blockers": [],
        "current_node": "preflight_configuration_check",
        "completed_nodes": list(state.completed_nodes) + ["preflight_configuration_check"],
    }


def _finish(state: ProductWorkflowState) -> dict[str, Any]:
    """Finalize the workflow execution."""
    return {
        "status": "ready_for_execution",
        "current_node": "finish",
        "completed_nodes": list(state.completed_nodes) + ["finish"],
    }


def _make_langgraph_node(node_def: Any) -> Any:
    """Adapt a @_register node function to LangGraph's state-update protocol."""
    node_name = node_def.name
    node_fn = node_def.fn

    def wrapper(state: ProductWorkflowState) -> dict[str, Any]:
        _start = perf_counter()
        _session = session_var.get()
        wf_repo = WorkflowRepository(_session) if _session else None
        node_run_id: str | None = None

        if wf_repo:
            input_snapshot = state.model_dump(mode="json")
            node_run = wf_repo.create_node_run(
                workflow_run_id=state.workflow_id,
                node_name=node_name,
                input_snapshot=input_snapshot,
            )
            node_run_id = node_run.id
            wf_repo.update_node_run_status(node_run.id, status="running")

        state.metadata_json["_session"] = _session
        product_mode = os.environ.get("APP_MODE", "").casefold() == "product"
        max_retries = _node_max_retries()
        attempt = 0
        try:
            while True:
                try:
                    result = node_fn(state)
                except Exception as exc:
                    if _is_langgraph_interrupt(exc):
                        raise
                    if attempt < max_retries:
                        if wf_repo and node_run_id:
                            wf_repo.increment_node_retry(node_run_id)
                        attempt += 1
                        continue
                    raise NodeExecutionError(
                        node_name,
                        f"Unhandled exception after {attempt + 1} attempt(s): {type(exc).__name__}: {exc}",
                    ) from exc

                retryable_status = product_mode and node_def.critical and result.status in {
                    NodeStatus.FAILED,
                    NodeStatus.DEGRADED,
                    NodeStatus.SKIPPED,
                }
                if retryable_status and attempt < max_retries:
                    if wf_repo and node_run_id:
                        wf_repo.increment_node_retry(node_run_id)
                    attempt += 1
                    continue
                break
        finally:
            state.metadata_json.pop("_session", None)

        _elapsed_s = perf_counter() - _start

        if wf_repo and node_run_id:
            status_map = {
                NodeStatus.COMPLETED: "completed",
                NodeStatus.DEGRADED: "degraded",
                NodeStatus.SKIPPED: "skipped",
            }
            wf_repo.update_node_run_status(
                node_run_id,
                status=status_map.get(result.status, "completed"),
                output_snapshot=result.state_updates,
                error_message=result.error_message,
            )

        fail_closed = product_mode and node_def.critical and result.status in {
            NodeStatus.FAILED,
            NodeStatus.DEGRADED,
            NodeStatus.SKIPPED,
        }
        if result.status == NodeStatus.FAILED or fail_closed:
            observe_node(node_name, "failed", _elapsed_s)
            if wf_repo and node_run_id:
                wf_repo.update_node_run_status(
                    node_run_id,
                    status="failed",
                    error_message=result.error_message or result.degraded_reason or f"Critical product node {node_name} did not complete",
                )
            raise NodeExecutionError(
                node_name,
                result.error_message or result.degraded_reason or f"Critical product node {node_name} did not complete",
            )

        observe_node(node_name, result.status, _elapsed_s)

        updates: dict[str, Any] = dict(result.state_updates or {})
        updates["current_node"] = node_name
        updates["completed_nodes"] = list(state.completed_nodes) + [node_name]

        if result.status == NodeStatus.DEGRADED:
            updates["degraded_nodes"] = list(state.degraded_nodes) + [node_name]

        return updates

    return wrapper


def build_workflow_graph(*, checkpointer: Any = None) -> Any | None:
    """Build and compile the full single-pipeline LangGraph workflow.

    All domain nodes registered via ``@_register`` in ``node_impl.py``
    are wired in order into the pipeline:
      preflight → load_startup_or_candidate → plan_search → collect_sources
      → extract_profile → validate_evidence → score_startup_probabilistic → diagnose_gaps
      → retrieve_nvidia_context → map_nvidia_technologies → rank_recommendations
      → generate_brief → run_quality_gates → generate_claims
      → match_activation_playbooks → generate_activation_dossier
      → run_product_quality → summarize_readiness → needs_review
      → apply_feedback_weights → write_decision_ledger → (finish | plan_missing_information)

    After ``needs_review``, ``apply_feedback_weights`` adjusts runtime weights
    based on human review feedback. If the review decision was
    ``"request_more_evidence"`` and iterations remain, the graph routes to
    ``plan_missing_information`` and then back through collection, extraction,
    validation, scoring, gap diagnosis and recommendations with changed inputs.

    Parameters
    ----------
    checkpointer:
        A LangGraph checkpointer (e.g. ``MemorySaver()``) for interrupt/resume
        support. When ``None`` (default) the graph runs without persistence.
    """
    if not LANGGRAPH_AVAILABLE or not WORKFLOW_NODES:
        return None

    graph = StateGraph(state_schema=ProductWorkflowState)

    graph.add_node("preflight_configuration_check", _preflight_configuration_check)
    graph.add_node("finish", _finish)

    for node_def in WORKFLOW_NODES:
        graph.add_node(node_def.name, _make_langgraph_node(node_def))

    # Explicit pipeline order — independent of @_register decoration order
    PIPELINE_ORDER = [
        "load_startup_or_candidate",
        "plan_search",
        "collect_sources",
        "extract_profile",
        "validate_evidence",
        "score_startup_probabilistic",
        "diagnose_gaps",
        "retrieve_nvidia_context",
        "enhance_contexts_with_techniques",
        "map_nvidia_technologies",
        "rank_recommendations",
        "rank_with_expected_utility",
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
    ]

    def _route_after_feedback(state: ProductWorkflowState) -> str:
        if state.review_decision == "request_more_evidence" and state.iteration_count < state.max_iterations:
            return "plan_missing_information"
        return "finish"

    graph.add_edge(START, "preflight_configuration_check")
    graph.add_edge("preflight_configuration_check", PIPELINE_ORDER[0])
    for i in range(len(PIPELINE_ORDER) - 1):
        graph.add_edge(PIPELINE_ORDER[i], PIPELINE_ORDER[i + 1])
    graph.add_conditional_edges(PIPELINE_ORDER[-1], _route_after_feedback)
    graph.add_edge("plan_missing_information", "collect_sources")
    graph.add_edge("finish", END)

    if checkpointer is not None:
        return graph.compile(checkpointer=checkpointer)
    return graph.compile()
