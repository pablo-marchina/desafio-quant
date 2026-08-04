"""Compatibilidade para imports antigos do broker Dramatiq.

O broker compartilhado agora mora em ``apps.api.src.shared.queue`` porque ele
nao pertence ao modulo scraping. Mantemos este reexport para nao quebrar
documentos/testes antigos durante a transicao.
"""

from apps.api.src.shared.queue.dramatiq_broker import (
    broker,
    check_redis_connection,
)
