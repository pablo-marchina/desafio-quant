"""Adapter do modulo ingestion para Orchestration V2."""

from uuid import UUID

from apps.api.src.modules.ingestion.application.public.ingested_reader import (
    IngestedDocumentReader,
)
from apps.api.src.modules.ingestion.application.public.ingestion_job_submitter import (
    IngestionJobSubmitter,
)
from apps.api.src.modules.orchestration.application.ports import (
    DocumentContentView,
    IngestionPort,
    StepStatus,
)


class IngestionModulePort(IngestionPort):
    def __init__(
        self,
        submitter: IngestionJobSubmitter,
        document_reader: IngestedDocumentReader,
    ) -> None:
        self._submitter = submitter
        self._document_reader = document_reader

    async def submit(
        self,
        scraping_result_id: UUID,
        *,
        source_type: str = "startup_evidence",
    ) -> UUID:
        return await self._submitter.submit(
            scraping_result_id,
            source_type=source_type,
        )

    async def get_status(self, job_id: UUID) -> StepStatus:
        status = await self._submitter.get_status(job_id)
        return StepStatus(
            is_done=status.status == "completed",
            is_failed=status.status == "failed",
            result_id=status.document_id,
            error_message=status.error_message,
        )

    async def get_document_content(
        self, scraping_result_id: UUID
    ) -> DocumentContentView | None:
        summary = await self._document_reader.get_by_scraping_result_id(
            scraping_result_id
        )
        if summary is None:
            return None
        return DocumentContentView(title=summary.title, clean_text=summary.clean_text)
