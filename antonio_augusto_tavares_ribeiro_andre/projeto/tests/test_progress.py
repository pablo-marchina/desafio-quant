"""Testes do progresso ao vivo + canal Redis (F2.10).

Tudo offline: o grafo já roda sem rede (M2/DoD) e o Redis é **injetado** (stub que
registra `publish`/serve mensagens). Exercita:
- `ProgressEvent`: contrato serializável round-trip (worker → SSE) + `progress_channel`;
- `_pct`: progresso pela posição na espinha (sentinela → None);
- `stream_pipeline` offline: um evento por nó (`running`) + terminal (`completed`, pct=100),
  `run_id` carimbado, estado final COMPLETED; sem `on_event` não quebra;
- `stream_pipeline` no interrupt HITL sync (F2.8): eventos param antes do briefing e o
  terminal vira `awaiting_review` (estado pausa em RUNNING);
- `RedisProgressPublisher`: `PUBLISH` no canal com o JSON; engole `RedisError` (best-effort);
- `subscribe_progress`: itera os eventos do canal até o terminal (`END_NODE`).
"""

from __future__ import annotations

import json

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from redis.exceptions import ConnectionError as RedisConnectionError

import packages.agents.human_review as hr
from packages.agents import (
    PIPELINE,
    ProgressEvent,
    RedisProgressPublisher,
    progress_channel,
    resume_pipeline,
    stream_pipeline,
    subscribe_progress,
)
from packages.agents.checkpoint import state_serde
from packages.agents.progress import END_NODE, _pct
from packages.schemas import HITLMode, RunStatus

# O serde allow-all emite um aviso advisory benigno por tipo (ver `state_serde`).
pytestmark = pytest.mark.filterwarnings("ignore:Deserializing unregistered type")


class _FakeSettings:
    def __init__(self, *, enabled: bool) -> None:
        self.hitl_enabled = enabled


# --- ProgressEvent / canal ----------------------------------------------------


def test_progress_event_round_trips() -> None:
    ev = ProgressEvent(run_id="r1", node="scraper", status="running", pct=20)
    restored = ProgressEvent.model_validate_json(ev.model_dump_json())
    assert restored.run_id == "r1"
    assert restored.node == "scraper"
    assert restored.status == "running"
    assert restored.pct == 20
    assert restored.ts == ev.ts  # ts preservado no transporte


def test_progress_channel_is_per_run() -> None:
    assert progress_channel("r1") == "tapi:progress:r1"
    assert progress_channel("r1") != progress_channel("r2")


def test_pct_tracks_pipeline_position() -> None:
    assert _pct(PIPELINE[0]) == 10  # 1/10
    assert _pct(PIPELINE[-1]) == 100  # 10/10
    assert _pct(END_NODE) is None  # sentinela não é nó da espinha


# --- stream_pipeline offline --------------------------------------------------


def test_stream_pipeline_emits_event_per_node_then_terminal() -> None:
    events: list[ProgressEvent] = []
    state = stream_pipeline("Acme AI", run_id="r1", on_event=events.append)

    per_node = [e for e in events if e.node != END_NODE]
    assert [e.node for e in per_node] == list(PIPELINE)  # um evento por nó, na ordem
    assert all(e.status == "running" for e in per_node)
    assert all(e.run_id == "r1" for e in events)

    terminal = events[-1]
    assert terminal.node == END_NODE
    assert terminal.status == RunStatus.COMPLETED.value
    assert terminal.pct == 100
    assert state.status is RunStatus.COMPLETED  # estado final devolvido (igual run_pipeline)


def test_stream_pipeline_without_sink_just_runs() -> None:
    # sem on_event nada é publicado (offline default) e o grafo roda igual ao run_pipeline.
    state = stream_pipeline("Acme AI", run_id="r1")
    assert state.status is RunStatus.COMPLETED


def test_stream_pipeline_terminal_is_awaiting_review_on_hitl_interrupt(monkeypatch) -> None:
    monkeypatch.setattr(hr, "get_settings", lambda: _FakeSettings(enabled=True))
    events: list[ProgressEvent] = []
    state = stream_pipeline(
        "Acme AI",
        run_id="run-hitl",
        hitl=HITLMode.SYNC,
        checkpointer=InMemorySaver(serde=state_serde()),
        on_event=events.append,
    )

    per_node = [e.node for e in events if e.node != END_NODE]
    assert per_node == list(PIPELINE[:8])  # parou antes de human_review/briefing
    terminal = events[-1]
    assert terminal.node == END_NODE
    assert terminal.status == RunStatus.AWAITING_REVIEW.value  # mapeado do interrupt (F2.8)
    assert state.status is RunStatus.RUNNING  # run pausado, não concluído


def test_resume_pipeline_finishes_paused_run(monkeypatch) -> None:
    monkeypatch.setattr(hr, "get_settings", lambda: _FakeSettings(enabled=True))
    saver = InMemorySaver(serde=state_serde())
    # 1) roda até o interrupt (pausa antes do human_review/briefing).
    paused = stream_pipeline("Acme AI", run_id="run-x", hitl=HITLMode.SYNC, checkpointer=saver)
    assert paused.status is RunStatus.RUNNING

    # 2) retoma com a decisão humana → completa, registra a decisão e emite o terminal.
    events: list[ProgressEvent] = []
    decision = {"approved": True, "nota": "ok"}
    state = resume_pipeline("run-x", decision, checkpointer=saver, on_event=events.append)

    assert state.status is RunStatus.COMPLETED
    assert state.trace["human_review"] == decision  # decisão auditável (F2.8)
    nodes = [e.node for e in events]
    assert "briefing" in nodes  # rodou só os nós restantes
    assert nodes[-1] == END_NODE
    assert events[-1].status == RunStatus.COMPLETED.value


# --- transporte Redis (cliente injetado) --------------------------------------


class _RecordingRedis:
    """Stub de `redis.Redis` que registra os `publish` (sem broker)."""

    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []

    def publish(self, channel: str, data: str) -> None:
        self.published.append((channel, data))


class _BrokenRedis:
    def publish(self, channel: str, data: str) -> None:
        raise RedisConnectionError("broker down")


def test_redis_publisher_publishes_event_json_to_channel() -> None:
    client = _RecordingRedis()
    publisher = RedisProgressPublisher(client)
    publisher(ProgressEvent(run_id="r1", node="scraper", status="running", pct=20))

    assert len(client.published) == 1
    channel, payload = client.published[0]
    assert channel == "tapi:progress:r1"
    assert json.loads(payload)["node"] == "scraper"  # evento serializado como JSON


def test_redis_publisher_is_best_effort_on_broker_error() -> None:
    # falha de broker não pode derrubar o run (progresso é telemetria).
    publisher = RedisProgressPublisher(_BrokenRedis())
    publisher(ProgressEvent(run_id="r1", node="scraper", status="running"))  # não levanta


class _FakePubSub:
    def __init__(self, messages: list[dict]) -> None:
        self._messages = list(messages)
        self.subscribed: list[str] = []
        self.closed = False

    def subscribe(self, channel: str) -> None:
        self.subscribed.append(channel)

    def get_message(
        self, *, ignore_subscribe_messages: bool, timeout: float | None = None
    ) -> dict | None:
        return self._messages.pop(0) if self._messages else None

    def close(self) -> None:
        self.closed = True


class _FakeRedisSub:
    def __init__(self, pubsub: _FakePubSub) -> None:
        self._pubsub = pubsub

    def pubsub(self) -> _FakePubSub:
        return self._pubsub


def test_subscribe_progress_yields_until_terminal() -> None:
    def _msg(node: str, status: str) -> dict:
        ev = ProgressEvent(run_id="r1", node=node, status=status)
        return {"type": "message", "data": ev.model_dump_json()}

    pubsub = _FakePubSub(
        [
            _msg("scraper", "running"),
            _msg("briefing", "running"),
            _msg(END_NODE, "completed"),
            _msg("nao_deve_chegar", "running"),  # após o terminal, não é consumido
        ]
    )
    client = _FakeRedisSub(pubsub)

    got = list(subscribe_progress(client, "r1"))

    assert [e.node for e in got] == ["scraper", "briefing", END_NODE]  # parou no terminal
    assert pubsub.subscribed == ["tapi:progress:r1"]
    assert pubsub.closed is True  # fechou o pubsub ao sair
