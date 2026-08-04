"""Avanca manualmente url_ingestion_jobs pelo caso de uso oficial.

Uso:
    venv\\Scripts\\python.exe scripts/advance_url_ingestion_jobs.py <job_id> [...]
"""

from __future__ import annotations

import asyncio
import sys
from uuid import UUID

from apps.api.src.modules.orchestration.domain.exceptions import (
    UrlIngestionStillProcessingError,
)
from apps.api.src.modules.orchestration.factories.orchestration_factory import (
    OrchestrationFactory,
)


async def main(job_ids: list[str]) -> None:
    use_case = OrchestrationFactory.create_advance_url_ingestion_job()
    for raw_job_id in job_ids:
        job_id = UUID(raw_job_id)
        try:
            await use_case.execute(job_id=job_id)
        except UrlIngestionStillProcessingError as exc:
            print(f"{job_id}\tprocessing\t{exc}")
        except Exception as exc:
            print(f"{job_id}\terror\t{type(exc).__name__}: {exc}")
        else:
            print(f"{job_id}\tadvanced")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
