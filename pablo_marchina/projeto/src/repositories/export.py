"""Export repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import ExportRecord


class ExportRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        analysis_run_id: str,
        action_brief_id: str | None = None,
        export_type: str,
        status: str = "pending",
        storage_path: str = "",
        content_hash: str = "",
        error_message: str | None = None,
    ) -> ExportRecord:
        record = ExportRecord(
            analysis_run_id=analysis_run_id,
            action_brief_id=action_brief_id,
            export_type=export_type,
            status=status,
            storage_path=storage_path,
            content_hash=content_hash,
            error_message=error_message,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def get(self, export_id: str) -> ExportRecord | None:
        statement = select(ExportRecord).where(ExportRecord.id == export_id)
        return self.session.scalar(statement)

    def list_for_run(self, analysis_run_id: str) -> list[ExportRecord]:
        statement = (
            select(ExportRecord)
            .where(ExportRecord.analysis_run_id == analysis_run_id)
            .order_by(ExportRecord.created_at.desc())
        )
        return list(self.session.scalars(statement))
