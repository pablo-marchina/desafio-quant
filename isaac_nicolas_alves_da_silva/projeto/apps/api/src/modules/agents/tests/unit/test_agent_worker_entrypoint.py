"""Testes da configuracao operacional do agent worker."""

from workers.agent_worker.run import build_worker_arguments


def test_worker_listens_only_to_agents_queue() -> None:
    arguments = build_worker_arguments()

    assert arguments[0] == "workers.agent_worker.tasks"
    assert arguments[arguments.index("--queues") + 1] == "agents"
    assert arguments[arguments.index("--processes") + 1] == "1"
