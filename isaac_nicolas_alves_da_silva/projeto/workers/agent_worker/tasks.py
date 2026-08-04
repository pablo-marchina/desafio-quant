"""Actors Dramatiq executados pelo worker de agentes."""

from uuid import UUID

import dramatiq

# Usamos o mesmo broker Redis compartilhado do sistema, mas em uma fila
# separada chamada ``agents``. Assim, scraper_worker e agent_worker podem rodar
# em processos diferentes e consumir filas diferentes.
from apps.api.src.shared.queue.dramatiq_broker import (
    broker,
)
from apps.api.src.modules.agents.factories.agents_factory import AgentsFactory
from apps.api.src.shared.logging import get_logger, log_job

logger = get_logger(__name__)


@dramatiq.actor(
    broker=broker,
    queue_name="agents",
    max_retries=3,
)
async def execute_agent_job(run_id: str) -> None:
    """Executa uma tarefa de agente usando a logica do modulo agents.

    O worker transporta apenas dados serializaveis. Ele nao implementa grafo,
    prompt, validacao semantica ou regras de negocio.
    """

    with log_job(logger, "agent run", agent_run_id=run_id):
        use_case = AgentsFactory.create_execute_agent_job()
        await use_case.execute(run_id=UUID(run_id))
