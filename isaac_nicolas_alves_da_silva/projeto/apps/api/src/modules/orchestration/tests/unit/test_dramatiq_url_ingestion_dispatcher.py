"""Testes do dispatcher Dramatiq de url ingestion sem depender de Redis real."""

from uuid import uuid4

import pytest
from dramatiq.brokers.stub import StubBroker

from apps.api.src.modules.orchestration.domain.exceptions import (
    UrlIngestionTaskDispatchError,
)
from apps.api.src.modules.orchestration.infrastructure.queue.dramatiq_url_ingestion_dispatcher import (
    DramatiqUrlIngestionJobPublisher,
    DramatiqUrlIngestionTaskDispatcher,
)


class RecordingPublisher:
    """Publisher minimo que registra os job_ids recebidos pelo teste."""

    def __init__(self) -> None:
        self.sent_job_ids: list[str] = []

    def send(self, job_id: str) -> object:
        self.sent_job_ids.append(job_id)
        return object()


class FailingPublisher:
    """Simula indisponibilidade do Redis durante a publicacao."""

    def send(self, job_id: str) -> object:
        raise ConnectionError("Redis indisponivel")


@pytest.mark.anyio
async def test_dispatch_sends_job_id_as_string() -> None:
    """O dispatcher deve transportar somente o UUID serializavel."""

    publisher = RecordingPublisher()
    dispatcher = DramatiqUrlIngestionTaskDispatcher(publisher)
    job_id = uuid4()

    await dispatcher.dispatch(job_id=job_id)

    assert publisher.sent_job_ids == [str(job_id)]


@pytest.mark.anyio
async def test_dispatch_translates_publisher_failure() -> None:
    """Falhas externas devem virar um erro conhecido pela aplicacao."""

    dispatcher = DramatiqUrlIngestionTaskDispatcher(FailingPublisher())

    with pytest.raises(UrlIngestionTaskDispatchError):
        await dispatcher.dispatch(job_id=uuid4())


def test_publisher_builds_message_for_orchestration_worker() -> None:
    """O modulo deve publicar sem precisar importar o worker externo."""

    broker = StubBroker()
    published_messages = []
    broker.enqueue = published_messages.append
    publisher = DramatiqUrlIngestionJobPublisher(broker)
    job_id = str(uuid4())

    publisher.send(job_id)

    assert len(published_messages) == 1
    assert published_messages[0].queue_name == "url_ingestion"
    assert published_messages[0].actor_name == "advance_url_ingestion_job"
    assert published_messages[0].args == (job_id,)
