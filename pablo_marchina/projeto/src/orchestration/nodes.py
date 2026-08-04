from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from src.orchestration.state import ProductWorkflowState


@dataclass
class NodeResult:
    status: str
    state_updates: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    degraded_reason: str | None = None


NodeFn = Callable[[ProductWorkflowState], NodeResult]


@dataclass
class NodeDefinition:
    name: str
    description: str
    fn: NodeFn
    critical: bool = False


NODE_NAMES: list[str] = []


def _register(name: str, description: str, critical: bool = False) -> Callable[[NodeFn], NodeFn]:
    def decorator(fn: NodeFn) -> NodeFn:
        WORKFLOW_NODES.append(NodeDefinition(name=name, description=description, fn=fn, critical=critical))
        NODE_NAMES.append(name)
        return fn

    return decorator


WORKFLOW_NODES: list[NodeDefinition] = []
