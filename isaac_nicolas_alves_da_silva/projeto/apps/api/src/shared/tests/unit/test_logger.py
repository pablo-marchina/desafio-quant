"""Testes do logger estruturado compartilhado (shared/logging)."""

import json
import logging

import pytest

from apps.api.src.shared.logging.logger import (
    JsonFormatter,
    bind_context,
    get_logger,
    log_job,
)


class ListHandler(logging.Handler):
    """Handler de teste: formata e guarda cada linha emitida.

    Formata dentro de ``emit()``, no mesmo momento em que um handler real
    formataria - ``_context`` e lido por ``JsonFormatter`` em tempo de
    formatacao, e o bloco ``bind_context()`` pode ja ter saido por tras
    quando o teste inspeciona o resultado depois.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setFormatter(JsonFormatter())
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))


def _capture(logger: logging.Logger) -> ListHandler:
    handler = ListHandler()
    logger.addHandler(handler)
    return handler


def test_get_logger_does_not_duplicate_handlers_on_repeated_calls() -> None:
    logger_a = get_logger("test.logger.idempotent")
    logger_b = get_logger("test.logger.idempotent")

    assert logger_a is logger_b
    assert len(logger_a.handlers) == 1


def test_json_formatter_includes_required_fields() -> None:
    logger = get_logger("test.logger.format")
    handler = _capture(logger)

    logger.info("job iniciado")

    payload = json.loads(handler.lines[0])

    assert payload["message"] == "job iniciado"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test.logger.format"
    assert "timestamp" in payload


def test_bind_context_injects_correlation_ids_into_log_output() -> None:
    logger = get_logger("test.logger.context")
    handler = _capture(logger)

    with bind_context(job_id="job-1", startup_id="startup-1"):
        logger.info("evidencia anexada")

    payload = json.loads(handler.lines[0])

    assert payload["job_id"] == "job-1"
    assert payload["startup_id"] == "startup-1"


def test_bind_context_does_not_leak_outside_the_block() -> None:
    logger = get_logger("test.logger.leak")
    handler = _capture(logger)

    with bind_context(job_id="job-1"):
        pass
    logger.info("fora do bloco")

    payload = json.loads(handler.lines[0])

    assert "job_id" not in payload


def test_nested_bind_context_merges_without_losing_outer_ids() -> None:
    logger = get_logger("test.logger.nested")
    handler = _capture(logger)

    with bind_context(job_id="job-1"):
        with bind_context(startup_id="startup-1"):
            logger.info("dentro do bloco aninhado")
        logger.info("apos saida do bloco interno")

    inner_payload = json.loads(handler.lines[0])
    outer_payload = json.loads(handler.lines[1])

    assert inner_payload["job_id"] == "job-1"
    assert inner_payload["startup_id"] == "startup-1"
    assert outer_payload["job_id"] == "job-1"
    assert "startup_id" not in outer_payload


class StillProcessingError(Exception):
    pass


def test_log_job_logs_start_and_finish_on_success() -> None:
    logger = get_logger("test.logger.job.success")
    handler = _capture(logger)

    with log_job(logger, "scraping job", job_id="job-1"):
        pass

    messages = [json.loads(line)["message"] for line in handler.lines]
    assert messages == ["scraping job started", "scraping job finished"]
    assert json.loads(handler.lines[0])["job_id"] == "job-1"


def test_log_job_logs_failure_and_reraises_unexpected_exceptions() -> None:
    logger = get_logger("test.logger.job.failure")
    handler = _capture(logger)

    with pytest.raises(ValueError):
        with log_job(logger, "scraping job", job_id="job-1"):
            raise ValueError("boom")

    levels = [json.loads(line)["level"] for line in handler.lines]
    assert levels == ["INFO", "ERROR"]


def test_log_job_logs_expected_retry_exceptions_as_info_not_failure() -> None:
    logger = get_logger("test.logger.job.retry")
    handler = _capture(logger)

    with pytest.raises(StillProcessingError):
        with log_job(
            logger,
            "url ingestion job",
            expected_retry_exceptions=(StillProcessingError,),
            job_id="job-1",
        ):
            raise StillProcessingError("still going")

    levels = [json.loads(line)["level"] for line in handler.lines]
    assert levels == ["INFO", "INFO"]
