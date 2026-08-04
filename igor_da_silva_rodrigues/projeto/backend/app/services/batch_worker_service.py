from __future__ import annotations

import time
from contextlib import contextmanager
from threading import Event, Thread

from app.core.observability import LOGGER
from app.services.batch_processing_service import BatchProcessingService


class BatchWorkerService:
    """Poll and execute durable batches outside the HTTP server process."""

    def __init__(
        self,
        service: BatchProcessingService,
        worker_id: str,
        heartbeat_seconds: float = 30.0,
        lease_seconds: int = 120,
    ) -> None:
        self.service = service
        self.repository = service.repository
        self.worker_id = worker_id
        self.heartbeat_seconds = heartbeat_seconds
        self.lease_seconds = lease_seconds

    def recover_stale(self, stale_after_minutes: int = 30) -> int:
        recovered = self.repository.recover_stale_batches(stale_after_minutes)
        if recovered:
            LOGGER.warning("stale_batches_recovered", worker_id=self.worker_id, count=recovered)
        return recovered

    def run_once(self) -> bool:
        batch = self.repository.claim_next_batch(self.worker_id, self.lease_seconds)
        if batch is None:
            return False
        batch_id = batch["id"]
        LOGGER.info("worker_batch_claimed", worker_id=self.worker_id, batch_id=batch_id)
        try:
            with self._continuous_heartbeat(self._uuid(batch_id)):
                self.service.run_batch(
                    batch_id=self._uuid(batch_id),
                    resume=True,
                    worker_id=self.worker_id,
                )
        except Exception as exc:
            self.repository.fail_batch(self._uuid(batch_id), str(exc))
            LOGGER.error(
                "worker_batch_failed",
                worker_id=self.worker_id,
                batch_id=batch_id,
                error=str(exc),
            )
        return True

    @contextmanager
    def _continuous_heartbeat(self, batch_id):
        stop = Event()

        def renew() -> None:
            while not stop.wait(self.heartbeat_seconds):
                try:
                    self.repository.heartbeat(batch_id, self.worker_id, self.lease_seconds)
                except Exception as exc:
                    LOGGER.error(
                        "worker_heartbeat_failed",
                        worker_id=self.worker_id,
                        batch_id=str(batch_id),
                        error=str(exc),
                    )

        thread = Thread(target=renew, name=f"heartbeat-{batch_id}", daemon=True)
        thread.start()
        try:
            yield
        finally:
            stop.set()
            thread.join(timeout=max(1.0, self.heartbeat_seconds + 1))

    def run_forever(self, stop_event: Event, poll_seconds: float = 5.0) -> None:
        LOGGER.info("worker_started", worker_id=self.worker_id, poll_seconds=poll_seconds)
        while not stop_event.is_set():
            processed = self.run_once()
            if not processed:
                stop_event.wait(poll_seconds)
        LOGGER.info("worker_stopped", worker_id=self.worker_id)

    @staticmethod
    def _uuid(value):
        from uuid import UUID

        return UUID(str(value))
