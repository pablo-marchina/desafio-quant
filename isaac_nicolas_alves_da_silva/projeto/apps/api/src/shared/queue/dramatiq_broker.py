"""Configuracao compartilhada do broker Dramatiq com Redis.

O broker nao pertence ao modulo scraping nem ao modulo agents. Ele e uma
infraestrutura transversal do sistema: varios workers podem usar o mesmo Redis,
mas cada worker consome sua propria fila.
"""

import asyncio

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import AsyncIO

from apps.api.src.config.settings import get_settings


# Redis transporta somente mensagens pequenas entre API e workers. O estado
# real de cada fluxo deve ficar nos bancos apropriados, nao na fila.
broker = RedisBroker(url=get_settings().redis_url)

# Actors Dramatiq sao sincronos por padrao. Este middleware mantem um event
# loop no worker para permitir tasks async.
broker.add_middleware(AsyncIO())

# Dramatiq usa um broker global para registrar actors e enviar mensagens.
dramatiq.set_broker(broker)


async def check_redis_connection() -> bool:
    """Verifica a conexao Redis sem bloquear o event loop da API."""

    return bool(await asyncio.to_thread(broker.client.ping))
