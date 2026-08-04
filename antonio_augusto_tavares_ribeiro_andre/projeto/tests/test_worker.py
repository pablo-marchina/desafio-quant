"""Testes do worker async (F2.10) — job RQ + enfileiramento.

Offline: o job recebe Redis/checkpointer/sessão/runner **injetados** (sem broker nem
Postgres). A **gravação** das saídas do run (run/company/score/recs) é da
`tests/test_worker_persistence.py`; aqui a sessão é injetada nula (no-op). Exercita:
- `run_graph_job`: roda o grafo de verdade (offline) com checkpointer nulo e um Redis
  stub → resumo `completed` e progresso publicado no canal (por nó + terminal);
- coerção de `mode`/`hitl` vindos como string (sobrevivem ao pickle da fila);
- `enqueue_run`: enfileira `run_graph_job` com `job_id=run_id` (casa run ↔ job ↔ canal)
  e devolve o `run_id`, passando só argumentos planos.
"""

from __future__ import annotations

import json
from contextlib import nullcontext

import pytest
from langgraph.checkpoint.memory import InMemorySaver

import packages.agents.human_review as hr
from apps.worker import enqueue_resume, enqueue_run, resume_graph_job, run_graph_job
from packages.agents.checkpoint import state_serde
from packages.agents.progress import END_NODE, stream_pipeline
from packages.schemas import ExecutionMode, HITLMode, RunStatus

# O grafo offline não toca o serde do checkpointer (passamos None); sem aviso a filtrar.
pytestmark = pytest.mark.filterwarnings("ignore:Deserializing unregistered type")


class _FakeSettings:
    def __init__(self, *, enabled: bool) -> None:
        self.hitl_enabled = enabled


class _RecordingRedis:
    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []

    def publish(self, channel: str, data: str) -> None:
        self.published.append((channel, data))


def _no_checkpointer():
    # contextmanager que entrega None: o grafo roda offline sem persistir (M2/DoD).
    return nullcontext(None)


def _no_session():
    # contextmanager que entrega None: o job roda offline sem gravar no banco (M2/DoD).
    return nullcontext(None)


# --- run_graph_job ------------------------------------------------------------


def test_run_graph_job_runs_graph_and_publishes_progress() -> None:
    redis = _RecordingRedis()
    summary = run_graph_job(
        "Acme AI",
        run_id="r1",
        redis_client=redis,
        open_checkpointer=_no_checkpointer,
        open_session=_no_session,
    )

    assert summary == {
        "run_id": "r1",
        "status": RunStatus.COMPLETED.value,
        "query": "Acme AI",
        "needs_review": False,
    }
    # publicou no canal do run: um por nó + o terminal.
    channels = {ch for ch, _ in redis.published}
    assert channels == {"tapi:progress:r1"}
    nodes = [json.loads(payload)["node"] for _, payload in redis.published]
    assert nodes[0] == "search_planner"
    assert nodes[-1] == END_NODE


def test_run_graph_job_coerces_str_mode_and_hitl() -> None:
    # a API/CLI podem mandar texto; o job aceita string e enum indistintamente.
    redis = _RecordingRedis()
    summary = run_graph_job(
        "fintechs AI em SP",
        run_id="r2",
        mode="discovery",
        hitl="auto",
        redis_client=redis,
        open_checkpointer=_no_checkpointer,
        open_session=_no_session,
    )
    assert summary["status"] == RunStatus.COMPLETED.value
    assert summary["run_id"] == "r2"


def test_run_graph_job_generates_run_id_when_absent() -> None:
    redis = _RecordingRedis()
    summary = run_graph_job(
        "Acme AI",
        redis_client=redis,
        open_checkpointer=_no_checkpointer,
        open_session=_no_session,
    )
    assert summary["run_id"]  # uuid gerado
    # o canal usa o mesmo run_id gerado.
    assert all(ch == f"tapi:progress:{summary['run_id']}" for ch, _ in redis.published)


# --- resume_graph_job ---------------------------------------------------------


def test_resume_graph_job_resumes_paused_run_and_publishes(monkeypatch) -> None:
    # 1) roda até o interrupt do HITL sync (pausa antes do briefing) numa thread persistida.
    monkeypatch.setattr(hr, "get_settings", lambda: _FakeSettings(enabled=True))
    saver = InMemorySaver(serde=state_serde())
    stream_pipeline("Acme AI", run_id="r-res", hitl=HITLMode.SYNC, checkpointer=saver)

    # 2) o job retoma com a decisão humana (mesmo checkpointer injetado) e publica o resto.
    redis = _RecordingRedis()
    summary = resume_graph_job(
        "r-res",
        {"approved": True},
        redis_client=redis,
        open_checkpointer=lambda: nullcontext(saver),
        open_session=_no_session,
    )

    assert summary["run_id"] == "r-res"
    assert summary["status"] == RunStatus.COMPLETED.value
    channels = {ch for ch, _ in redis.published}
    assert channels == {"tapi:progress:r-res"}
    assert json.loads(redis.published[-1][1])["node"] == END_NODE  # terminal no fim


# --- enqueue_run --------------------------------------------------------------


class _RecordingQueue:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def enqueue(self, func, *args, **kwargs) -> None:  # noqa: ANN001 — assina como o RQ
        self.calls.append({"func": func, "args": args, "kwargs": kwargs})


def test_enqueue_run_enqueues_job_with_run_id_as_job_id() -> None:
    queue = _RecordingQueue()
    run_id = enqueue_run("Acme AI", queue=queue, run_id="r1")

    assert run_id == "r1"
    assert len(queue.calls) == 1
    call = queue.calls[0]
    assert call["func"] is run_graph_job
    assert call["args"] == ("Acme AI",)
    assert call["kwargs"]["run_id"] == "r1"
    assert call["kwargs"]["job_id"] == "r1"  # casa job RQ ↔ run ↔ canal
    # só argumentos planos viajam na fila (enum vira string).
    assert call["kwargs"]["mode"] == ExecutionMode.SINGLE_COMPANY.value
    assert call["kwargs"]["hitl"] == HITLMode.SYNC.value


def test_enqueue_run_generates_run_id_when_absent() -> None:
    queue = _RecordingQueue()
    run_id = enqueue_run("Acme AI", queue=queue)
    assert run_id
    assert queue.calls[0]["kwargs"]["job_id"] == run_id


def test_enqueue_run_sets_generous_job_timeout() -> None:
    # Run real (coleta + LLM com reasoning + retries F7.6) passa do default de 180s do RQ e era
    # morto no meio (JobTimeoutException). O enqueue passa um teto generoso (> default do RQ).
    queue = _RecordingQueue()
    enqueue_run("Acme AI", queue=queue, run_id="r1")
    assert queue.calls[0]["kwargs"]["job_timeout"] > 180


def test_enqueue_resume_uses_distinct_resume_job_id() -> None:
    queue = _RecordingQueue()
    run_id = enqueue_resume("r1", {"approved": True}, queue=queue)

    assert run_id == "r1"
    call = queue.calls[0]
    assert call["func"] is resume_graph_job
    assert call["args"] == ("r1", {"approved": True})
    job_id = call["kwargs"]["job_id"]
    assert job_id == "r1-resume"  # distinto do job original (job_id=run_id)
    # RQ valida o job_id (só letras/números/_/-): `:` estourava ValueError no resume ao vivo.
    assert ":" not in job_id
    import re

    assert re.fullmatch(r"[A-Za-z0-9_-]+", job_id)
