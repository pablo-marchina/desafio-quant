"""Logger estruturado (JSON) com correlation ids via contextvars.

Cobre a regra 10 do CLAUDE.md: todo log deve carregar os IDs relevantes
(request_id/job_id/startup_id/document_id/agent_run_id). Em vez de passar
esses IDs em cada chamada de log, ``bind_context()`` os fixa no contexto da
task asyncio atual; toda chamada de log feita dentro do bloco (em qualquer
profundidade de call stack) os inclui automaticamente.

``contextvars.ContextVar`` e seguro entre tasks asyncio concorrentes: cada
task criada por ``asyncio.create_task``/``TaskGroup`` recebe uma copia do
contexto do momento da criacao, e mudancas feitas dentro de uma task nao
"escapam" para outras tasks irmas ou para o contexto do worker que a criou.
"""

import contextvars
import json
import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

_context: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "log_context", default={}
)

_RESERVED_RECORD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)


class JsonFormatter(logging.Formatter):
    """Formata cada registro como uma linha JSON, com correlation ids."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            **_context.get(),
        }

        extra_attrs = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _RESERVED_RECORD_ATTRS
        }
        payload.update(extra_attrs)

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def get_logger(name: str) -> logging.Logger:
    """Devolve um logger configurado com saida JSON em stdout.

    Idempotente: chamar de novo com o mesmo ``name`` nao duplica handlers.
    """

    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


@contextmanager
def bind_context(**correlation_ids: Any) -> Iterator[None]:
    """Adiciona ids de correlacao a todo log emitido dentro do bloco.

    Uso tipico no topo de um use case ou actor de worker::

        with bind_context(job_id=str(job.id), startup_id=str(startup_id)):
            logger.info("job iniciado")
            ... # qualquer log emitido aqui dentro, em qualquer funcao
            ... # chamada a partir daqui, carrega job_id/startup_id
    """

    current = _context.get()
    token = _context.set({**current, **correlation_ids})
    try:
        yield
    finally:
        _context.reset(token)


@contextmanager
def log_job(
    logger: logging.Logger,
    job_name: str,
    *,
    expected_retry_exceptions: tuple[type[Exception], ...] = (),
    **correlation_ids: Any,
) -> Iterator[None]:
    """Loga inicio/fim/falha de um job de worker, com correlation ids.

    ``expected_retry_exceptions`` cobre excecoes que sinalizam "ainda
    processando, o Dramatiq vai reentregar" (ex.
    ``UrlIngestionStillProcessingError``, ``EmbeddingJobPartiallyFailedError``)
    - sao logadas em INFO, nao como falha, mas ainda relancadas para o
    Dramatiq decidir o retry. Qualquer outra excecao e logada como falha
    real (``logger.exception``, com traceback) e tambem relancada. Este
    helper nunca decide retry nem suprime excecao - so loga.
    """

    with bind_context(**correlation_ids):
        logger.info("%s started", job_name)
        try:
            yield
        except expected_retry_exceptions as error:
            logger.info("%s not finished yet, will retry: %s", job_name, error)
            raise
        except Exception:
            logger.exception("%s failed", job_name)
            raise
        else:
            logger.info("%s finished", job_name)
