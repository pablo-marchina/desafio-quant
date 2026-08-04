"""Testes do dispatcher Dramatiq sem depender de um Redis real."""

from uuid import uuid4

import pytest
from dramatiq.brokers.stub import StubBroker

from apps.api.src.modules.scraping.infrastructure.queue.dramatiq_task_dispatcher import (
    DramatiqJobPublisher,
    DramatiqTaskDispatcher,
)
from apps.api.src.modules.scraping.domain.exceptions import TaskDispatchError


class FakeJobActor:
    """Actor minimo que registra as mensagens recebidas pelo teste."""

    def __init__(self) -> None:
        self.sent_job_ids: list[str] = []

    def send(self, job_id: str) -> object:
        self.sent_job_ids.append(job_id)
        return object()


class FailingJobActor:
    """Simula indisponibilidade do Redis durante a publicacao."""

    def send(self, job_id: str) -> object:
        raise ConnectionError("Redis indisponivel")


@pytest.mark.anyio
async def test_dispatch_sends_job_id_as_string() -> None:
    """O dispatcher deve transportar somente o UUID serializavel."""

    actor = FakeJobActor()
    dispatcher = DramatiqTaskDispatcher(actor)
    job_id = uuid4()

    await dispatcher.dispatch(job_id)

    assert actor.sent_job_ids == [str(job_id)]


@pytest.mark.anyio
async def test_dispatch_translates_publisher_failure() -> None:
    """Falhas externas devem virar um erro conhecido pela aplicacao."""

    dispatcher = DramatiqTaskDispatcher(FailingJobActor())

    with pytest.raises(TaskDispatchError):
        await dispatcher.dispatch(uuid4())


def test_publisher_builds_message_for_scraping_worker() -> None:
    """O modulo deve publicar sem precisar importar o worker externo."""

    broker = StubBroker()
    published_messages = []
    broker.enqueue = published_messages.append
    publisher = DramatiqJobPublisher(broker)
    job_id = str(uuid4())

    publisher.send(job_id)

    assert len(published_messages) == 1
    assert published_messages[0].queue_name == "scraping"
    assert published_messages[0].actor_name == "execute_scraping_job"
    assert published_messages[0].args == (job_id,)
