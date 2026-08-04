"""Adapter de Orchestration V2 para NVIDIA Knowledge."""

from uuid import UUID

from apps.api.src.modules.nvidia_knowledge.application.ports import (
    NvidiaKnowledgeUrlIngestionSubmitter,
)
from apps.api.src.modules.orchestration.application.dto import (
    CreateUrlIngestionJobInput,
)
from apps.api.src.modules.orchestration.application.use_cases.create_url_ingestion_job import (
    CreateUrlIngestionJob,
)


class UrlIngestionSubmitterAdapter(NvidiaKnowledgeUrlIngestionSubmitter):
    def __init__(self, use_case: CreateUrlIngestionJob) -> None:
        self._use_case = use_case

    async def submit(
        self,
        url: str,
        *,
        source_type: str,
    ) -> UUID:
        view = await self._use_case.execute(
            CreateUrlIngestionJobInput(
                url=url,
                source_type=source_type,
            )
        )
        return view.id
