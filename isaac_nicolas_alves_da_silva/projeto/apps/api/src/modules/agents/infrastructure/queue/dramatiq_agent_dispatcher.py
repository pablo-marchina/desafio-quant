"""Dispatcher que publica execucoes de agentes em uma fila Dramatiq."""

import asyncio
from typing import Protocol
from uuid import UUID

from dramatiq import Message
from dramatiq.broker import Broker

from apps.api.src.modules.agents.application.ports import AgentTaskDispatcher
from apps.api.src.modules.agents.domain.exceptions import AgentTaskDispatchError


class AgentJobActor(Protocol):
    """Parte minima de um actor necessaria para publicar agent jobs."""

    def send(self, run_id: str) -> object:
        """Publica a mensagem serializavel."""


class DramatiqAgentJobPublisher:
    """Publica mensagem compativel com o worker de agentes."""

    def __init__(
        self,
        broker: Broker,
        *,
        actor_name: str = "execute_agent_job",
        queue_name: str = "agents",
    ) -> None:
        self.broker = broker
        self.actor_name = actor_name
        self.queue_name = queue_name

    def send(self, run_id: str) -> object:
        """Cria a mensagem Dramatiq sem importar o worker externo."""

        message = Message(
            queue_name=self.queue_name,
            actor_name=self.actor_name,
            args=(run_id,),
            kwargs={},
            options={},
        )

        return self.broker.enqueue(message)


class DramatiqAgentTaskDispatcher(AgentTaskDispatcher):
    """Publica agent jobs em Redis/Dramatiq sem bloquear o event loop."""

    def __init__(self, actor: AgentJobActor) -> None:
        self.actor = actor

    async def dispatch(
        self,
        *,
        run_id: UUID,
    ) -> None:
        """Envia a execucao para a fila ``agents``."""

        try:
            await asyncio.to_thread(self.actor.send, str(run_id))
        except Exception as error:
            raise AgentTaskDispatchError(
                "Nao foi possivel publicar o job na fila de agentes."
            ) from error
