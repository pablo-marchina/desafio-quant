from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Callable


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def langgraph_runtime_available() -> bool:
    try:
        from langgraph.graph import END, START, StateGraph  # noqa: F401
    except Exception:
        return False
    return True


def graph_engine_status() -> dict[str, Any]:
    langgraph_available = langgraph_runtime_available()
    return {
        "engine": "LangGraph" if langgraph_available else "SequentialStateGraph",
        "langgraph_available": langgraph_available,
        "fallback_engine": "SequentialStateGraph",
        "compatibility": (
            "langgraph_nominal_available"
            if langgraph_available
            else "langgraph_compatible_fallback"
        ),
    }


@dataclass
class PipelineStep:
    name: str
    agent: str
    status: str = "running"
    started_at: str = field(default_factory=utc_now_iso)
    finished_at: str | None = None
    duration_ms: int | None = None
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    _start: float = field(default_factory=perf_counter, repr=False)

    def finish(
        self,
        *,
        status: str = "completed",
        summary: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.status = status
        self.finished_at = utc_now_iso()
        self.duration_ms = round((perf_counter() - self._start) * 1000)
        if summary:
            self.summary = summary
        if metadata:
            self.metadata.update(metadata)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "agent": self.agent,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": self.duration_ms,
            "summary": self.summary,
            "metadata": self.metadata,
        }


class PipelineTrace:
    def __init__(self) -> None:
        self.steps: list[PipelineStep] = []

    def start(self, name: str, agent: str) -> PipelineStep:
        step = PipelineStep(name=name, agent=agent)
        self.steps.append(step)
        return step

    def add(
        self,
        *,
        name: str,
        agent: str,
        status: str = "completed",
        summary: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> PipelineStep:
        step = self.start(name, agent)
        step.finish(status=status, summary=summary, metadata=metadata)
        return step

    def as_list(self) -> list[dict[str, Any]]:
        return [step.to_dict() for step in self.steps]


@dataclass(frozen=True)
class GraphNode:
    name: str
    agent: str
    handler: Callable[[Any], None]
    retries: int = 0
    retry_exceptions: tuple[type[BaseException], ...] = ()
    condition: Callable[[Any], bool] | None = None


class SequentialStateGraph:
    """Small state-graph runner used when the deployment does not install LangGraph.

    The API mirrors the project need: named nodes, shared mutable state, optional
    conditions, retry metadata and a pipeline trace compatible with the briefing.
    """

    def __init__(self, trace: PipelineTrace) -> None:
        self.trace = trace
        self.nodes: list[GraphNode] = []

    def add_node(
        self,
        name: str,
        agent: str,
        handler: Callable[[Any], None],
        *,
        retries: int = 0,
        retry_exceptions: tuple[type[BaseException], ...] = (),
        condition: Callable[[Any], bool] | None = None,
    ) -> None:
        self.nodes.append(
            GraphNode(
                name=name,
                agent=agent,
                handler=handler,
                retries=retries,
                retry_exceptions=retry_exceptions,
                condition=condition,
            )
        )

    def run(self, state: Any) -> Any:
        for node in self.nodes:
            self._run_node(state, node)
        return state

    def _run_node(self, state: Any, node: GraphNode) -> None:
        if node.condition is not None and not node.condition(state):
            self.trace.add(
                name=node.name,
                agent=node.agent,
                status="skipped",
                summary="No ignorado pela condicao do grafo.",
                metadata={"graph_node": node.name},
            )
            return

        attempt = 0
        while True:
            attempt += 1
            step = self.trace.start(node.name, node.agent)
            if hasattr(state, "current_step"):
                state.current_step = step
            try:
                node.handler(state)
                if step.status == "running":
                    step.finish(
                        summary="No executado.",
                        metadata={"graph_node": node.name, "attempt": attempt},
                    )
                else:
                    step.metadata.setdefault("graph_node", node.name)
                    step.metadata.setdefault("attempt", attempt)
                break
            except Exception as error:
                retryable = node.retry_exceptions and isinstance(
                    error,
                    node.retry_exceptions,
                )
                should_retry = retryable and attempt <= node.retries
                step.finish(
                    status="retrying" if should_retry else "failed",
                    summary=(
                        "Falha transiente; tentando novamente."
                        if should_retry
                        else "No falhou."
                    ),
                    metadata={
                        "graph_node": node.name,
                        "attempt": attempt,
                        "error": str(error),
                        "error_type": type(error).__name__,
                    },
                )
                if not should_retry:
                    raise
            finally:
                if hasattr(state, "current_step"):
                    state.current_step = None


class LangGraphStateGraph(SequentialStateGraph):
    """LangGraph-backed runner used when the optional runtime is installed.

    Node handlers keep the same shared-state contract used by the fallback
    runner. This makes local/offline demos stable while still executing through
    LangGraph's compiled graph in environments that install the dependency.
    """

    def run(self, state: Any) -> Any:
        try:
            from langgraph.graph import END, START, StateGraph
        except Exception:
            return super().run(state)

        workflow = StateGraph(dict)

        for graph_node in self.nodes:
            workflow.add_node(
                graph_node.name,
                self._langgraph_handler(graph_node),
            )

        previous = START
        for graph_node in self.nodes:
            workflow.add_edge(previous, graph_node.name)
            previous = graph_node.name
        workflow.add_edge(previous, END)

        compiled = workflow.compile()
        result = compiled.invoke({"state": state})
        return result.get("state", state) if isinstance(result, dict) else state

    def _langgraph_handler(self, node: GraphNode) -> Callable[[dict[str, Any]], dict[str, Any]]:
        def handler(payload: dict[str, Any]) -> dict[str, Any]:
            state = payload["state"]
            self._run_node(state, node)
            return payload

        return handler


def create_state_graph(trace: PipelineTrace) -> SequentialStateGraph:
    if langgraph_runtime_available():
        return LangGraphStateGraph(trace)
    return SequentialStateGraph(trace)
