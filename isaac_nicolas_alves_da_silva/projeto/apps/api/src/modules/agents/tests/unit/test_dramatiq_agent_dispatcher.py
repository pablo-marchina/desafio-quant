"""Testes do dispatcher Dramatiq de agentes sem Redis real."""

from uuid import uuid4

import pytest
from dramatiq.brokers.stub import StubBroker

from apps.api.src.modules.agents.domain.exceptions import AgentTaskDispatchError
from apps.api.src.modules.agents.infrastructure.queue.dramatiq_agent_dispatcher import (
    DramatiqAgentJobPublisher,
    DramatiqAgentTaskDispatcher,
)


class FakeAgentJobActor:
    """Actor minimo que registra mensagens recebidas."""

    def __init__(self) -> None:
        self.sent_run_ids: list[str] = []

    def send(self, run_id: str) -> object:
        self.sent_run_ids.append(run_id)
        return object()


class FailingAgentJobActor:
    """Simula falha externa durante publicacao."""

    def send(self, run_id: str) -> object:
        raise ConnectionError("Redis indisponivel")


@pytest.mark.anyio
async def test_dispatch_sends_only_run_id() -> None:
    actor = FakeAgentJobActor()
    dispatcher = DramatiqAgentTaskDispatcher(actor)
    run_id = uuid4()

    await dispatcher.dispatch(run_id=run_id)

    assert actor.sent_run_ids == [str(run_id)]


@pytest.mark.anyio
async def test_dispatch_translates_publisher_failure() -> None:
    dispatcher = DramatiqAgentTaskDispatcher(FailingAgentJobActor())

    with pytest.raises(AgentTaskDispatchError):
        await dispatcher.dispatch(run_id=uuid4())


def test_publisher_builds_message_for_agent_worker() -> None:
    broker = StubBroker()
    published_messages = []
    broker.enqueue = published_messages.append
    publisher = DramatiqAgentJobPublisher(broker)
    run_id = str(uuid4())

    publisher.send(run_id)

    assert len(published_messages) == 1
    assert published_messages[0].queue_name == "agents"
    assert published_messages[0].actor_name == "execute_agent_job"
    assert published_messages[0].args == (run_id,)
