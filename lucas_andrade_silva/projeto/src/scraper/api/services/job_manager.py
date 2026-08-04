from __future__ import annotations

import logging
import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from threading import RLock
from typing import Any, Protocol
from uuid import uuid4

from scraper.api.schemas import JobStatus

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int], None]
JobCallable = Callable[[ProgressCallback], Any]


@dataclass
class Job:
    job_id: str
    job_type: str
    startup_id: str
    status: JobStatus
    progress: int
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    result: Any = None


class JobStore(Protocol):
    """Persistence boundary that can later be implemented with Redis/RQ."""

    def create(self, job: Job) -> None: ...

    def get(self, job_id: str) -> Job | None: ...

    def update(self, job_id: str, **changes: Any) -> Job: ...


class InMemoryJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = RLock()

    def create(self, job: Job) -> None:
        with self._lock:
            self._jobs[job.job_id] = deepcopy(job)

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return deepcopy(job) if job else None

    def update(self, job_id: str, **changes: Any) -> Job:
        with self._lock:
            job = self._jobs[job_id]
            for field, value in changes.items():
                setattr(job, field, value)
            return deepcopy(job)


class JobManager:
    def __init__(
        self,
        store: JobStore | None = None,
        max_workers: int | None = None,
    ) -> None:
        self.store = store or InMemoryJobStore()
        workers = max_workers or int(os.getenv("API_JOB_WORKERS", "4"))
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, workers),
            thread_name_prefix="startup-api-job",
        )

    def submit(
        self,
        job_type: str,
        startup_id: str,
        operation: JobCallable,
    ) -> Job:
        job = Job(
            job_id=str(uuid4()),
            job_type=job_type,
            startup_id=startup_id,
            status=JobStatus.QUEUED,
            progress=0,
            created_at=datetime.now(UTC),
        )
        self.store.create(job)
        self._executor.submit(self._execute, job.job_id, operation)
        logger.info(
            "Job queued",
            extra={"job_id": job.job_id, "job_type": job_type},
        )
        return job

    def get(self, job_id: str) -> Job | None:
        return self.store.get(job_id)

    def as_dict(self, job: Job) -> dict[str, Any]:
        return asdict(job)

    def _execute(self, job_id: str, operation: JobCallable) -> None:
        self.store.update(
            job_id,
            status=JobStatus.RUNNING,
            progress=1,
            started_at=datetime.now(UTC),
        )

        def report_progress(value: int) -> None:
            current = self.store.get(job_id)
            if current and current.status == JobStatus.RUNNING:
                self.store.update(job_id, progress=max(1, min(99, int(value))))

        try:
            result = operation(report_progress)
        except Exception as error:
            logger.exception("Job failed", extra={"job_id": job_id})
            self.store.update(
                job_id,
                status=JobStatus.FAILED,
                finished_at=datetime.now(UTC),
                error=str(error),
            )
            return

        self.store.update(
            job_id,
            status=JobStatus.COMPLETED,
            progress=100,
            finished_at=datetime.now(UTC),
            result=result,
        )
        logger.info("Job completed", extra={"job_id": job_id})

    def shutdown(self, wait: bool = False) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=False)

