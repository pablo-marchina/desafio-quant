from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.observability import LOGGER


ResultT = TypeVar("ResultT")


def execute_with_retry(
    operation: Callable[[], ResultT],
    stage: str,
    retryable: tuple[type[BaseException], ...] = (Exception,),
    max_attempts: int = 3,
    wait_multiplier: float = 2.0,
) -> tuple[ResultT, int]:
    attempts = 0

    def before_sleep(retry_state: Any) -> None:
        LOGGER.warning(
            "stage_retry",
            stage=stage,
            attempt=retry_state.attempt_number,
            error=str(retry_state.outcome.exception()),
            next_wait_seconds=retry_state.next_action.sleep,
        )

    retrying = Retrying(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=wait_multiplier, min=wait_multiplier, max=8),
        retry=retry_if_exception_type(retryable),
        before_sleep=before_sleep,
        reraise=True,
    )
    for attempt in retrying:
        with attempt:
            attempts = attempt.retry_state.attempt_number
            return operation(), attempts
    raise RuntimeError(f"Etapa {stage} terminou sem resultado")
