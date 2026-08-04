"""Reenfileira as startups presentes em analyses_export.json.

Uso:
    venv\\Scripts\\python.exe scripts/requeue_exported_startup_analyses.py
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from uuid import UUID

from apps.api.src.modules.orchestration.application.dto import (
    CreateUrlIngestionJobInput,
)
from apps.api.src.modules.orchestration.factories.orchestration_factory import (
    OrchestrationFactory,
)


ROOT = Path(__file__).resolve().parents[1]
EXPORT_PATH = ROOT / "analyses_export.json"


async def main() -> None:
    data = json.loads(EXPORT_PATH.read_text(encoding="utf-8"))
    startups = data["startups"]["rows"]
    use_case = OrchestrationFactory.create_create_url_ingestion_job()

    created: list[tuple[str, str, str]] = []
    for row in startups:
        url = row.get("website_url")
        startup_id = row.get("id")
        if not url or not startup_id:
            continue

        view = await use_case.execute(
            CreateUrlIngestionJobInput(
                url=url,
                source_type="startup_evidence",
                startup_id=UUID(startup_id),
            )
        )
        created.append((str(view.id), view.url, str(view.startup_id)))

    print(f"CREATED {len(created)}")
    for job_id, url, startup_id in created:
        print(f"{job_id}\t{startup_id}\t{url}")


if __name__ == "__main__":
    asyncio.run(main())
