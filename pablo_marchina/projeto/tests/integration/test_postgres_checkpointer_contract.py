from __future__ import annotations

import os
from typing import TypedDict
from uuid import uuid4

import pytest
from langgraph.graph import END, START, StateGraph

from src.orchestration.runner import (
    _build_postgres_checkpointer,
    _is_postgres_checkpointer,
    reset_checkpointer_runtime,
)


class _CheckpointState(TypedDict):
    value: int


def _compile_graph(checkpointer):  # noqa: ANN001, ANN202
    builder = StateGraph(_CheckpointState)
    builder.add_node("increment", lambda state: {"value": state["value"] + 1})
    builder.add_edge(START, "increment")
    builder.add_edge("increment", END)
    return builder.compile(checkpointer=checkpointer)


@pytest.mark.integration
def test_langgraph_checkpoint_survives_runtime_reinitialization(monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = os.environ.get("LANGGRAPH_POSTGRES_URL", "").strip()
    if not database_url:
        pytest.skip("LANGGRAPH_POSTGRES_URL is not configured")

    monkeypatch.setenv("APP_MODE", "product")
    reset_checkpointer_runtime()

    first_saver = _build_postgres_checkpointer()
    assert first_saver is not None
    assert _is_postgres_checkpointer(first_saver)

    thread_id = f"release-contract-{uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}
    first_graph = _compile_graph(first_saver)
    assert first_graph.invoke({"value": 0}, config)["value"] == 1

    # Simulate an API process restart. A new PostgresSaver and connection must
    # recover the checkpoint written by the first runtime instance.
    reset_checkpointer_runtime()
    second_saver = _build_postgres_checkpointer()
    assert second_saver is not None
    assert second_saver is not first_saver
    second_graph = _compile_graph(second_saver)
    recovered = second_graph.get_state(config)

    assert recovered.values["value"] == 1
    assert recovered.next == ()
