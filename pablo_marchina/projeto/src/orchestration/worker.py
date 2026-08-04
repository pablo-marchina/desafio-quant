"""Durable worker for queued product workflows."""

from __future__ import annotations

import logging
import os
import signal
import time
from dataclasses import dataclass

from src.database.session import initialize_product_database, product_session
from src.orchestration.service import WorkflowOrchestrationService
from src.repositories.workflow import WorkflowRepository

logger = logging.getLogger("nvidia_radar.workflow_worker")


@dataclass
class WorkerState:
    stopping: bool = False


def _claim_next() -> str | None:
    with product_session() as session:
        run = WorkflowRepository(session).claim_next_queued_workflow()
        return run.id if run is not None else None


def _execute(workflow_id: str) -> None:
    try:
        with product_session() as session:
            WorkflowOrchestrationService(session).run_existing_workflow(workflow_id)
            persisted = WorkflowRepository(session).get_workflow_run(workflow_id)
            raw_status = getattr(persisted.status, "value", persisted.status) if persisted is not None else "unknown"
            status = str(raw_status).casefold()
            error = persisted.error_message if persisted is not None else None
            if status == "failed":
                logger.error("workflow_finished_failed workflow_id=%s error=%s", workflow_id, error or "unknown")
            elif status == "degraded":
                logger.warning("workflow_finished_degraded workflow_id=%s", workflow_id)
            else:
                logger.info("workflow_finished workflow_id=%s status=%s", workflow_id, status)
    except Exception as exc:
        logger.exception("workflow_worker_exception workflow_id=%s", workflow_id)
        with product_session() as session:
            WorkflowRepository(session).fail_workflow(
                workflow_id,
                error_message=f"Worker execution failed: {exc}",
            )


def run_worker() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    initialize_product_database()
    poll_seconds = max(0.25, float(os.environ.get("WORKFLOW_WORKER_POLL_SECONDS", "2")))
    state = WorkerState()

    def request_stop(signum: int, _frame: object) -> None:
        logger.info("worker_stop_requested signal=%s", signum)
        state.stopping = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    logger.info("workflow_worker_started poll_seconds=%s", poll_seconds)

    while not state.stopping:
        workflow_id = _claim_next()
        if workflow_id is None:
            time.sleep(poll_seconds)
            continue
        logger.info("workflow_claimed workflow_id=%s", workflow_id)
        _execute(workflow_id)

    logger.info("workflow_worker_stopped")


if __name__ == "__main__":
    run_worker()
